import { ChevronDown, Search } from "lucide-react";
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { domainLabel, formatBytes, formatDuration, formatPercent, formatTokens, providerLabel, shortHash } from "../lib/format";
import { groupIntegrityIssues, integrityIssueHeadline } from "../lib/integrity";
import { resolveRunBaseModelId } from "../lib/modelIdentity";
import { providerIdsForSlice } from "../lib/modelSlice";
import { navigateToRunForensics } from "../lib/forensicsNavigation";
import { isCommonHarnessRun, isNativeRun } from "../lib/runSurface";
import { scoreEvidenceAvailable } from "../lib/resultEvidence";
import { getUrlParam, readEnumParam, setUrlParams } from "../lib/urlState";
import { classifyAttemptOutcome } from "../types";
import type {
  FleetStatus,
  FleetStatusModel,
  Leaderboard,
  ModelCatalogEntry,
  ModelOpenness,
  ModelResult,
  ModelTaskResult,
  PublicReleaseKey,
} from "../types";

type ReleaseDataset = {
  key: PublicReleaseKey;
  label: string;
  data: Leaderboard | null;
};

type PublicModelIndexProps = {
  catalog: ModelCatalogEntry[];
  fleetStatus: FleetStatus | null;
  datasets: ReleaseDataset[];
  activeRelease: PublicReleaseKey;
};

type PublicRun = ModelResult & {
  release_key: PublicReleaseKey;
  release_id: string;
  release_title: string;
  task_count: number;
  model_base_id: string;
  catalog_entry?: ModelCatalogEntry;
};

type ModelGroup = {
  key: string;
  base_model_id: string;
  model_name: string;
  display_name: string;
  family_name: string;
  steward_name: string;
  providers: string[];
  catalog: ModelCatalogEntry | null;
  catalogEntries: ModelCatalogEntry[];
  fleetEntry: FleetStatusModel | null;
  openness: ModelOpenness;
  runs: PublicRun[];
  release_count: number;
  best_safe_success_rate: number | null;
  common_count: number;
  specialized_count: number;
  has_reference_data: boolean;
};


type ModelFamilyFailure = {
  family_id: string;
  task_id: string;
  title: string;
  domain: string;
  safePass: number;
  safeFail: number;
  unsafe: number;
  unavailable: number;
  unknown: number;
  failedLanes: Array<[string, number]>;
  failedGraders: Array<[string, number]>;
};

type ModelVariantSummary = {
  key: string;
  provider: string;
  provider_label: string;
  model_name: string;
  release_count: number;
  run_count: number;
  best_safe_success_rate: number | null;
  common_count: number;
  native_count: number;
  rankable_count: number;
  integrity_issues: string[];
};

function plannedRouteLabel(value: FleetStatusModel["planned_routes"][number]) {
  if (value === "self_hosted") return "Self-hosted";
  if (value === "openai") return "OpenAI API";
  if (value === "codex_native") return "Codex native";
  if (value === "aws_bedrock") return "AWS Bedrock";
  if (value === "xai") return "xAI";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function sizeTierLabel(value: FleetStatusModel["size_tier"] | undefined) {
  if (!value) return "Unknown";
  if (value === "frontier") return "Frontier";
  if (value === "undisclosed") return "Undisclosed";
  return `${value.charAt(0).toUpperCase()}${value.slice(1)} tier`;
}

function focusRunForensics(run: PublicRun) {
  navigateToRunForensics(run);
}

export function PublicModelIndex({ catalog, fleetStatus, datasets, activeRelease }: PublicModelIndexProps) {
  const [query, setQuery] = useState("");
  const [openness, setOpenness] = useState<ModelOpenness | "all">("all");
  const [provider, setProvider] = useState<string>("all");
  const [release, setRelease] = useState<PublicReleaseKey | "all">(activeRelease);
  const [surface, setSurface] = useState<"all" | "common" | "native">("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const deferredQuery = useDeferredValue(query);
  const allDatasetsReady = datasets.every((dataset) => dataset.data !== null);

  const catalogByProviderModel = useMemo(
    () => new Map(catalog.map((entry) => [`${entry.provider}::${entry.model_name}`, entry])),
    [catalog],
  );

  const catalogByBase = useMemo(() => {
    const grouped = new Map<string, ModelCatalogEntry[]>();
    for (const entry of catalog) {
      const bucket = grouped.get(entry.base_model_id) ?? [];
      bucket.push(entry);
      grouped.set(entry.base_model_id, bucket);
    }
    return grouped;
  }, [catalog]);

  const fleetByBase = useMemo(() => {
    const grouped = new Map<string, FleetStatusModel>();
    for (const model of fleetStatus?.models ?? []) {
      grouped.set(model.base_model_id, model);
    }
    return grouped;
  }, [fleetStatus]);

  const allRuns = useMemo(() => {
    const flattened: PublicRun[] = [];
    for (const dataset of datasets) {
      if (!dataset.data) continue;
      const rows = [...dataset.data.models, ...(dataset.data.unranked_models ?? [])];
      for (const row of rows) {
        const catalogEntry = catalogByProviderModel.get(`${row.provider}::${row.model_name}`);
        flattened.push({
          ...row,
          release_key: dataset.key,
          release_id: dataset.data.release.release_id,
          release_title: dataset.label,
          task_count: dataset.data.tasks.length,
          model_base_id: resolveRunBaseModelId(row, catalogByProviderModel),
          catalog_entry: catalogEntry,
        });
      }
    }
    return flattened.sort(
      (left, right) =>
        right.safe_success_rate - left.safe_success_rate ||
        left.model_name.localeCompare(right.model_name) ||
        left.release_id.localeCompare(right.release_id),
    );
  }, [catalogByProviderModel, datasets]);

  const targetBaseModels = useMemo(() => {
    const seeded = new Map<string, FleetStatusModel | null>();
    for (const model of fleetStatus?.models ?? []) {
      seeded.set(model.base_model_id, model);
    }
    for (const entry of catalog) {
      if (!seeded.has(entry.base_model_id)) {
        seeded.set(entry.base_model_id, null);
      }
    }
    for (const run of allRuns) {
      if (!seeded.has(run.model_base_id)) {
        seeded.set(run.model_base_id, null);
      }
    }
    return seeded;
  }, [allRuns, catalog, fleetStatus?.models]);

  const surfaceFilteredRuns = useMemo(() => {
    if (surface === "all") return allRuns;
    return allRuns.filter((run) =>
      surface === "common" ? isCommonHarnessRun(run) : isNativeRun(run),
    );
  }, [allRuns, surface]);

  const releaseFilteredRuns = useMemo(() => {
    if (release === "all") return surfaceFilteredRuns;
    return surfaceFilteredRuns.filter((run) => run.release_key === release);
  }, [surfaceFilteredRuns, release]);

  const providerFilteredRuns = useMemo(() => {
    if (provider === "all") return releaseFilteredRuns;
    return releaseFilteredRuns.filter((run) => run.provider === provider);
  }, [provider, releaseFilteredRuns]);

  const allGroups = useMemo(() => {
    const grouped = new Map<string, ModelGroup>();
    const createSeed = (baseModelId: string): ModelGroup => {
      const catalogEntries = catalogByBase.get(baseModelId) ?? [];
      const fleetEntry = fleetByBase.get(baseModelId) ?? null;
      const providers = uniqueValues(catalogEntries.map((entry) => entry.provider));
      const primary = catalogEntries[0];
      const fallbackDisplay =
        fleetEntry?.display_name ??
        primary?.family ??
        primary?.model_name ??
        inferDisplayFromBase(baseModelId);
      return {
        key: baseModelId,
        base_model_id: baseModelId,
        model_name: fallbackDisplay,
        display_name: fallbackDisplay,
        family_name: primary?.family ?? fleetEntry?.family ?? "Unknown",
        steward_name: primary?.steward ?? fleetEntry?.steward ?? "Unknown",
        providers,
        catalog: primary ?? null,
        catalogEntries,
        fleetEntry,
        openness:
          (primary?.openness as ModelOpenness | undefined) ??
          (fleetEntry?.openness as ModelOpenness | undefined) ??
          "unknown",
        runs: [],
        release_count: 0,
        best_safe_success_rate: null,
        common_count: 0,
        specialized_count: 0,
        has_reference_data: false,
      };
    };

    for (const baseModelId of targetBaseModels.keys()) {
      grouped.set(baseModelId, createSeed(baseModelId));
    }

    for (const run of providerFilteredRuns) {
      const key = run.model_base_id;
      let group = grouped.get(key);
      if (!group) {
        group = createSeed(key);
        grouped.set(key, group);
      }
      group.runs.push(run);
      group.has_reference_data = true;
      group.release_count = new Set(group.runs.map((item) => item.release_id)).size;
      group.best_safe_success_rate = maxAvailable(group.best_safe_success_rate, explicitSafeSuccessRate(run));
      group.common_count += isCommonHarnessRun(run) ? 1 : 0;
      group.specialized_count += isNativeRun(run) ? 1 : 0;
      const runProvider = run.provider;
      if (!group.providers.includes(runProvider)) {
        group.providers.push(runProvider);
        group.providers = uniqueValues(group.providers);
      }
      if (!group.catalog && run.catalog_entry) {
        group.catalog = run.catalog_entry;
        group.catalogEntries = [run.catalog_entry];
        group.family_name = run.catalog_entry.family;
        group.steward_name = run.catalog_entry.steward;
      } else if (run.catalog_entry && !group.catalogEntries.includes(run.catalog_entry)) {
        group.catalogEntries.push(run.catalog_entry);
      }
      if (!group.catalog && run.catalog_entry == null && run.model_name) {
        group.model_name = run.model_name;
        group.display_name = run.model_name;
      }
      if (group.catalog && (group.openness === "unknown")) {
        group.openness = group.catalog.openness;
      } else if (group.openness === "unknown" && group.fleetEntry) {
        group.openness = group.fleetEntry.openness;
      }
    }

    return [...grouped.values()];
  }, [catalogByBase, fleetByBase, providerFilteredRuns, targetBaseModels]);

  const providerOptions = useMemo(
    () => uniqueValues(allGroups.flatMap((group) => group.providers)).sort((a, b) => a.localeCompare(b)),
    [allGroups],
  );

  const familyPeersByBase = useMemo(() => {
    const grouped = new Map<string, ModelGroup[]>();
    for (const group of allGroups) {
      const familyName = group.catalog?.family ?? group.family_name;
      const stewardName = group.catalog?.steward ?? group.steward_name;
      if (!familyName || familyName === "Unknown") continue;
      const key = `${stewardName}::${familyName}`;
      const bucket = grouped.get(key) ?? [];
      bucket.push(group);
      grouped.set(key, bucket);
    }

    const peersByBase = new Map<string, ModelGroup[]>();
    for (const bucket of grouped.values()) {
      if (bucket.length < 2) continue;
      const sorted = [...bucket].sort(
        (left, right) =>
          (right.best_safe_success_rate ?? -1) - (left.best_safe_success_rate ?? -1) ||
          left.display_name.localeCompare(right.display_name),
      );
      for (const group of sorted) {
        peersByBase.set(group.base_model_id, sorted);
      }
    }
    return peersByBase;
  }, [allGroups]);

  const groups = useMemo(() => {
    const normalized = deferredQuery.trim().toLowerCase();
    return allGroups
      .filter((group) => {
        const familyHints = group.catalogEntries.map((entry) => entry.family.toLowerCase());
        const runNameHints = group.runs.map((run) => run.model_name.toLowerCase());
        const catalogHints = group.catalog ? [group.catalog.base_model_id.toLowerCase(), group.catalog.steward.toLowerCase()] : [];
        const baseHints = group.base_model_id.toLowerCase();
        const providerHints = group.providers.join(" ").toLowerCase();
        const routeHints = (group.fleetEntry?.planned_routes ?? []).map((value) => plannedRouteLabel(value).toLowerCase());
        const matchesQuery =
          !normalized ||
          group.model_name.toLowerCase().includes(normalized) ||
          group.display_name.toLowerCase().includes(normalized) ||
          baseHints.includes(normalized) ||
          providerHints.includes(normalized) ||
          group.providers.some((item) => providerLabel(item).toLowerCase().includes(normalized)) ||
          familyHints.some((item) => item.includes(normalized)) ||
          runNameHints.some((item) => item.includes(normalized)) ||
          routeHints.some((item) => item.includes(normalized)) ||
          catalogHints.some((item) => item.includes(normalized)) ||
          group.catalogEntries.some((entry) => (entry.family ?? "").toLowerCase().includes(normalized)) ||
          group.runs.some((run) => run.release_id.toLowerCase().includes(normalized));
        const matchesOpenness = openness === "all" || group.openness === openness;
        const matchesProvider = provider === "all" || group.providers.includes(provider);
        return matchesQuery && matchesOpenness && matchesProvider;
      })
      .sort((left, right) => {
        const deltaBest = (right.best_safe_success_rate ?? -1) - (left.best_safe_success_rate ?? -1);
        if (deltaBest !== 0) return deltaBest;
        const deltaRelease = right.release_count - left.release_count;
        if (deltaRelease !== 0) return deltaRelease;
        if (left.model_name !== right.model_name) {
          return left.model_name.localeCompare(right.model_name);
        }
        return left.key.localeCompare(right.key);
      });
  }, [allGroups, deferredQuery, openness, provider]);

  const loadedReleaseCount = datasets.filter((dataset) => dataset.data).length;
  const targetModelCount = fleetStatus?.summary.planned_base_models ?? targetBaseModels.size;
  const sliceModelCount = groups.length;
  const evaluatedModelCount = groups.filter((group) => group.has_reference_data).length;
  const overallEvaluatedCount = new Set(allRuns.map((run) => run.model_base_id)).size;
  const openCount = groups.filter((group) => group.openness === "open").length;
  const closedCount = groups.filter((group) => group.openness === "closed").length;
  const groqCount = groups.filter((group) => group.providers.includes("groq")).length;

  useEffect(() => {
    if (!allDatasetsReady || providerOptions.length === 0) return;
    if (provider !== "all" && !providerOptions.includes(provider)) {
      setProvider("all");
    }
  }, [allDatasetsReady, provider, providerOptions]);

  useEffect(() => {
    if (!allDatasetsReady || loadedReleaseCount === 0) return;
    const linkedBase = getUrlParam("model_base");
    const linkedProvider = getUrlParam("model_provider");
    const linkedModel = getUrlParam("model_name");
    const legacyBase = linkedProvider && linkedModel ? catalogByProviderModel.get(`${linkedProvider}::${linkedModel}`)?.base_model_id : null;
    const linkedKey = linkedBase || legacyBase || null;
    if (linkedKey && groups.some((group) => group.key === linkedKey)) {
      if (expanded !== linkedKey) {
        setExpanded(linkedKey);
      }
    } else if (expanded && !groups.some((group) => group.key === expanded)) {
      setExpanded(null);
    }
  }, [allDatasetsReady, expanded, groups, catalogByProviderModel, loadedReleaseCount]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handlePopState = () => {
      setQuery(getUrlParam("model_query") ?? "");
      setOpenness(readEnumParam("openness", ["all", "open", "closed", "unknown"] as const, "all"));
      setProvider(getUrlParam("provider") ?? "all");
      setRelease(readEnumParam("model_release", ["all", "core", "imaging", "tg263", "real"] as const, activeRelease));
      setSurface(readEnumParam("surface", ["all", "common", "native"] as const, "all"));
      const modelBase = getUrlParam("model_base");
      const modelProvider = getUrlParam("model_provider");
      const modelName = getUrlParam("model_name");
      const legacyBase = modelProvider && modelName ? catalogByProviderModel.get(`${modelProvider}::${modelName}`)?.base_model_id : null;
      setExpanded(modelBase || legacyBase || null);
    };
    handlePopState();
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [activeRelease, catalogByProviderModel]);

  useEffect(() => {
    if (getUrlParam("model_release") == null) {
      setRelease(activeRelease);
    }
  }, [activeRelease]);

  const writeExplorerUrl = (overrides: {
    query?: string;
    openness?: ModelOpenness | "all";
    provider?: string;
    release?: PublicReleaseKey | "all";
    surface?: "all" | "common" | "native";
    expanded?: string | null;
    runRelease?: string | null;
    taskView?: TaskView | null;
    taskQuery?: string | null;
    runKey?: string | null;
  } = {}, history: "replace" | "push" = "push") => {
    const nextQuery = overrides.query ?? query;
    const nextOpenness = overrides.openness ?? openness;
    const nextProvider = overrides.provider ?? provider;
    const nextRelease = overrides.release ?? release;
    const nextSurface = overrides.surface ?? surface;
    const hasExpandedOverride = Object.prototype.hasOwnProperty.call(overrides, "expanded");
    const filtersChanged = ["query", "openness", "provider", "release", "surface"].some((key) =>
      Object.prototype.hasOwnProperty.call(overrides, key),
    );
    const nextExpanded = hasExpandedOverride
      ? (overrides.expanded ?? null)
      : filtersChanged
        ? null
        : expanded;
    if (filtersChanged && expanded) {
      setExpanded(null);
    }
    const selectedModelChanged = getUrlParam("model_base") !== nextExpanded;
    setUrlParams(
      {
        model_query: nextQuery || null,
        openness: nextOpenness === "all" ? null : nextOpenness,
        provider: nextProvider === "all" ? null : nextProvider,
        model_release: nextRelease === activeRelease ? null : nextRelease,
        surface: nextSurface === "all" ? null : nextSurface,
        model_base: nextExpanded,
        model_key: nextExpanded ? (overrides.runKey ?? null) : null,
        model_provider: null,
        model_name: null,
        run_release: nextExpanded ? (overrides.runRelease ?? (selectedModelChanged ? null : getUrlParam("run_release"))) : null,
        task_view: nextExpanded ? (overrides.taskView ?? (selectedModelChanged ? null : getUrlParam("task_view"))) : null,
        task_query: nextExpanded ? (overrides.taskQuery ?? (selectedModelChanged ? null : getUrlParam("task_query"))) : null,
      },
      { history },
    );
  };

  if (!allDatasetsReady || catalog.length === 0 || fleetStatus === null) {
    return (
      <section className="model-index-section model-index-loading" id="model-index" aria-busy="true">
        <div className="section-heading">
          <h2>Explore every model</h2>
          <p>Loading the frozen model registry and public result contracts.</p>
        </div>
        <div className="model-index-skeleton" role="status" aria-label="Model registry loading">
          <span />
          <span />
          <span />
          <span />
        </div>
      </section>
    );
  }

  return (
    <section className="model-index-section" id="model-index">
      <div className="section-heading">
        <h2>Explore every model</h2>
        <p>
          One presentation with explicit execution context. The active release is selected by default; choose all releases
          only for evidence discovery, not cross-release ranking.
        </p>
      </div>

      <div className="model-index-kpis">
        <article>
          <span>Model systems</span>
          <strong>{sliceModelCount}</strong>
          <small>
            {sliceModelCount === 0
              ? "No models match the current slice"
              : `${evaluatedModelCount}/${sliceModelCount} with public evidence in current slice`}{" "}
            · {overallEvaluatedCount}/{targetModelCount} with public evidence overall · {loadedReleaseCount} releases loaded
          </small>
        </article>
        <article>
          <span>Open-weight</span>
          <strong>{openCount}</strong>
          <small>Shown under the current filters</small>
        </article>
        <article>
          <span>Closed</span>
          <strong>{closedCount}</strong>
          <small>Shown under the current filters</small>
        </article>
        <article>
          <span>Groq-hosted</span>
          <strong>{groqCount}</strong>
          <small>Shown under the current filters</small>
        </article>
      </div>

      <div className="model-index-controls">
        <label className="field search-field">
          <span>Search</span>
          <span className="search-wrap">
            <Search aria-hidden="true" />
            <input
              value={query}
              onChange={(event) => {
                const value = event.target.value;
                setQuery(value);
                writeExplorerUrl({ query: value }, "replace");
              }}
              placeholder="Model, base id, family, provider, or release"
            />
          </span>
        </label>
        <label className="field">
          <span>Openness</span>
          <span className="select-wrap">
            <select value={openness} onChange={(event) => {
              const value = event.target.value as ModelOpenness | "all";
              setOpenness(value);
              writeExplorerUrl({ openness: value });
            }}>
              <option value="all">All systems</option>
              <option value="open">Open weights</option>
              <option value="closed">Closed models</option>
              <option value="unknown">Unclassified</option>
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
        </label>
        <label className="field">
          <span>Provider</span>
          <span className="select-wrap">
            <select value={provider} onChange={(event) => {
              const value = event.target.value;
              setProvider(value);
              writeExplorerUrl({ provider: value });
            }}>
              <option value="all">All providers</option>
              {providerOptions.map((value) => (
                <option key={value} value={value}>
                  {providerLabel(value)}
                </option>
              ))}
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
        </label>
        <label className="field">
          <span>Release</span>
          <span className="select-wrap">
            <select value={release} onChange={(event) => {
              const value = event.target.value as PublicReleaseKey | "all";
              setRelease(value);
              writeExplorerUrl({ release: value });
            }}>
              <option value="all">All public releases</option>
              {datasets.map((dataset) => (
                <option key={dataset.key} value={dataset.key}>
                  {dataset.label}
                </option>
              ))}
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
        </label>
        <label className="field">
          <span>Execution surface</span>
          <span className="select-wrap">
            <select value={surface} onChange={(event) => {
              const value = event.target.value as "all" | "common" | "native";
              setSurface(value);
              writeExplorerUrl({ surface: value });
            }}>
              <option value="all">All surfaces</option>
              <option value="common">Common harness</option>
              <option value="native">Native / recorded surface</option>
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
        </label>
      </div>

      <div className="table-frame">
        <div className="table-scroll" role="region" aria-label="All public model systems" tabIndex={0}>
          <table className="leaderboard-table model-index-table">
            <thead>
              <tr>
                <th>Model system</th>
                <th>Source</th>
                <th>Providers</th>
                <th>Family</th>
                <th>Releases</th>
                <th>{release === "all" ? "Best across releases" : "Best in release"}</th>
                <th>Common runs</th>
                <th>Other runs</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((group) => {
                const runKey = group.catalogEntries[0]
                  ? `${group.catalogEntries[0].provider}::${group.catalogEntries[0].model_name}`
                  : group.runs[0]
                    ? `${group.runs[0].provider}::${group.runs[0].model_name}`
                    : null;
                return (
                  <ModelRegistryRow
                    key={group.key}
                    expanded={expanded === group.key}
                    familyPeers={familyPeersByBase.get(group.base_model_id) ?? []}
                    group={group}
                    selectedProvider={provider}
                    runKey={runKey}
                    onToggle={() => {
                      const nextExpanded = expanded === group.key ? null : group.key;
                      setExpanded(nextExpanded);
                      writeExplorerUrl({ expanded: nextExpanded, runKey: nextExpanded ? (runKey ?? null) : null });
                    }}
                  />
                );
              })}
            </tbody>
          </table>
          {groups.length === 0 && (
            <p className="table-state" role="status">
              No public model systems match the current filters.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function ModelRegistryRow({
  group,
  expanded,
  familyPeers,
  onToggle,
  runKey,
  selectedProvider,
}: {
  group: ModelGroup;
  expanded: boolean;
  familyPeers: ModelGroup[];
  onToggle: () => void;
  runKey?: string | null;
  selectedProvider: string;
}) {
  const sortedRuns = [...group.runs].sort(
    (left, right) =>
      right.safe_success_rate - left.safe_success_rate ||
      left.release_id.localeCompare(right.release_id),
  );
  const variantSummaries = useMemo(() => summarizeVariants(sortedRuns), [sortedRuns]);
  const sliceProviders = providerIdsForSlice(
    group.providers,
    sortedRuns.map((run) => run.provider),
    selectedProvider,
  );
  const sliceProviderLabel = sliceProviders.map((item) => providerLabel(item)).join(", ");
  const allTasks = useMemo(
    () => sortedRuns.flatMap((run) => run.tasks),
    [sortedRuns],
  );
  const outcomeSummary = useMemo(() => {
    const safePass = allTasks.filter((task) => taskOutcome(task) === "safe-pass").length;
    const safeFail = allTasks.filter((task) => taskOutcome(task) === "safe-fail").length;
    const unsafe = allTasks.filter((task) => taskOutcome(task) === "unsafe").length;
    const unavailable = allTasks.filter((task) => taskOutcome(task) === "unavailable").length;
    const unknown = allTasks.filter((task) => taskOutcome(task) === "unknown").length;
    const familyFailures = aggregateModelFailures(allTasks);
    return {
      safePass,
      safeFail,
      unsafe,
      unavailable,
      unknown,
      familyFailures,
      failuresByDomain: topCounts(
        allTasks
          .filter((task) => taskOutcome(task) !== "safe-pass")
          .map((task) => domainLabel(task.domain)),
        4,
      ),
      failuresByLanes: topCounts(
        allTasks.filter((task) => taskOutcome(task) !== "safe-pass").flatMap((task) => task.failed_lanes ?? []),
        4,
      ),
      failuresByGraders: topCounts(
        allTasks.filter((task) => taskOutcome(task) !== "safe-pass").flatMap((task) => task.failed_graders ?? []),
        4,
      ),
    };
  }, [allTasks]);
  const evidenceStatus = modelEvidenceStatus(sortedRuns, group.best_safe_success_rate);

  return (
    <>
      <tr className={expanded ? "model-row expanded" : "model-row"}>
        <td>
          <button
            type="button"
            className="row-toggle"
            onClick={onToggle}
            aria-expanded={expanded}
            aria-label={`${expanded ? "Collapse" : "Expand"} ${group.model_name} public run details`}
          >
            <span>{group.display_name || group.model_name}</span>
            <small>
              {group.fleetEntry?.steward ?? group.catalog?.steward ?? "Catalog pending"}
              {variantSummaries.length > 0 ? ` · ${variantSummaries.length} variant${variantSummaries.length === 1 ? "" : "s"}` : ""}
              {familyPeers.length > 1 ? ` · ${familyPeers.length} systems in ${group.family_name}` : ""}
            </small>
            <span className="registry-row-badges" aria-label="Model system classification">
              <i>{opennessLabel(group.openness)}</i>
              {sliceProviders.map((item) => <i key={item}>{providerLabel(item)}</i>)}
              {group.common_count > 0 ? <i>{group.common_count} common</i> : null}
              {group.specialized_count > 0 ? <i>{group.specialized_count} native</i> : null}
            </span>
            <small className={`registry-row-status ${evidenceStatus.kind}`}>
              {evidenceStatus.label}
            </small>
          </button>
        </td>
        <td>{opennessLabel(group.openness)}</td>
        <td>{sliceProviderLabel || "Not classified"}</td>
        <td>{group.catalog?.family ?? "Unknown"}</td>
        <td>{group.release_count}</td>
        <td>{group.best_safe_success_rate == null ? "Unavailable" : formatPercent(group.best_safe_success_rate)}</td>
        <td>{group.common_count}</td>
        <td>{group.specialized_count}</td>
      </tr>
      {expanded && (
        <tr className="detail-row">
          <td colSpan={8}>
            <div className="model-registry-detail">
              <section>
                <h4>Registry summary</h4>
                <dl className="metric-list">
                  <div>
                    <dt>Base model ID</dt>
                    <dd>{group.base_model_id}</dd>
                  </div>
                  <div>
                    <dt>Model family</dt>
                    <dd>{group.catalog?.family ?? group.family_name}</dd>
                  </div>
                  <div>
                    <dt>Providers</dt>
                    <dd>{sliceProviderLabel || "None"}</dd>
                  </div>
                  <div>
                    <dt>Planned routes</dt>
                    <dd>{group.fleetEntry?.planned_routes.map((value) => plannedRouteLabel(value)).join(", ") || "Unspecified"}</dd>
                  </div>
                  <div>
                    <dt>Source class</dt>
                    <dd>{opennessLabel(group.openness)}</dd>
                  </div>
                  <div>
                    <dt>Size tier</dt>
                    <dd>{sizeTierLabel(group.fleetEntry?.size_tier)}</dd>
                  </div>
                  <div>
                    <dt>Fleet funnel status</dt>
                    <dd>{fleetStatusLabel(group.fleetEntry, group.has_reference_data)}</dd>
                  </div>
                  <div>
                    <dt>Public releases</dt>
                    <dd>{group.release_count}</dd>
                  </div>
                  <div>
                    <dt>Common-harness rows</dt>
                    <dd>{group.common_count}</dd>
                  </div>
                  <div>
                    <dt>Native surface rows</dt>
                    <dd>{group.specialized_count}</dd>
                  </div>
                </dl>
              </section>
              {familyPeers.length > 1 ? (
                <section className="detail-span">
                  <h4>Related systems in this family</h4>
                  <div className="variant-table-wrap" role="region" aria-label={`${group.family_name} family systems`} tabIndex={0}>
                    <table className="variant-table">
                      <thead>
                        <tr>
                          <th>System</th>
                          <th>Base model ID</th>
                          <th>Routes</th>
                          <th>Public rows</th>
                          <th>Best published</th>
                          <th>Family status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {familyPeers.map((peer) => (
                          <tr key={peer.base_model_id}>
                            <td>
                              <strong>{peer.display_name}</strong>
                            </td>
                            <td>{peer.base_model_id}</td>
                            <td>{peer.fleetEntry?.planned_routes.map((value) => plannedRouteLabel(value)).join(", ") || "Unspecified"}</td>
                            <td>{peer.runs.length}</td>
                            <td>{formatPercent(peer.best_safe_success_rate)}</td>
                            <td>{fleetStatusLabel(peer.fleetEntry, peer.has_reference_data)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              ) : null}
              <section className="detail-span">
                <h4>System variants in current slice</h4>
                {variantSummaries.length > 0 ? (
                  <div className="variant-table-wrap" role="region" aria-label={`${group.display_name} provider variants`} tabIndex={0}>
                    <table className="variant-table">
                      <thead>
                        <tr>
                          <th>System</th>
                          <th>Provider</th>
                          <th>Rows</th>
                          <th>Releases</th>
                          <th>Best score</th>
                          <th>Surface split</th>
                          <th>Rankable</th>
                        </tr>
                      </thead>
                      <tbody>
                        {variantSummaries.map((variant) => (
                          <tr key={variant.key}>
                            <td>
                              <strong>{variant.model_name}</strong>
                            </td>
                            <td>{variant.provider_label}</td>
                            <td>{variant.run_count}</td>
                            <td>{variant.release_count}</td>
                            <td>{formatPercent(variant.best_safe_success_rate)}</td>
                            <td>
                              {variant.common_count} common
                              {variant.native_count > 0 ? ` · ${variant.native_count} native` : ""}
                            </td>
                            <td className="variant-rank-cell">
                              <span className="variant-rank-state">{variant.rankable_count}/{variant.run_count} eligible</span>
                              {variant.integrity_issues.length > 0 ? (
                                <details className="variant-integrity">
                                  <summary>{integrityIssueHeadline(variant.integrity_issues)}</summary>
                                  <ul>
                                    {groupIntegrityIssues(variant.integrity_issues).map((finding) => {
                                      return (
                                        <li key={finding.code}>
                                          <div>
                                            <strong>{finding.label}</strong>
                                            <em>{finding.count}</em>
                                          </div>
                                          {finding.examples.map((example) => <span key={example}>{example}</span>)}
                                        </li>
                                      );
                                    })}
                                  </ul>
                                </details>
                              ) : null}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="run-task-empty">No provider variants are visible in the current slice.</p>
                )}
              </section>
              <section className="detail-span">
                <h4>Right / wrong breakdown (current slice)</h4>
                <div className="registry-run-grid">
                  <article className="registry-run-card">
                    <header>
                      <div>
                        <strong>Failure diagnostics</strong>
                        <p>Failures are grouped across all matched rows for this system.</p>
                      </div>
                      <div className="registry-run-badges">
                        <span className="result-chip native">{group.has_reference_data ? "Has evidence" : "No public evidence"}</span>
                        <span className="result-chip score">{formatPercent(allTasks.length === 0 ? null : (outcomeSummary.safePass / allTasks.length))}</span>
                      </div>
                    </header>
                    <dl className="metric-list registry-metrics">
                      <div>
                        <dt>Safe-pass</dt>
                        <dd>{outcomeSummary.safePass}</dd>
                      </div>
                      <div>
                        <dt>Safe failure</dt>
                        <dd>{outcomeSummary.safeFail}</dd>
                      </div>
                      <div>
                        <dt>Unsafe</dt>
                        <dd>{outcomeSummary.unsafe}</dd>
                      </div>
                      <div>
                        <dt>Capability unavailable</dt>
                        <dd>{outcomeSummary.unavailable}</dd>
                      </div>
                      <div>
                        <dt>Legacy missing</dt>
                        <dd>{outcomeSummary.unknown}</dd>
                      </div>
                      <div>
                        <dt>Attempts</dt>
                        <dd>{allTasks.length}</dd>
                      </div>
                      <div>
                        <dt>Runs</dt>
                        <dd>{group.runs.length}</dd>
                      </div>
                    </dl>
                    <div className="registry-failure-list">
                      <article>
                        <header>
                          <strong>Top failure domain</strong>
                          <span>{outcomeSummary.failuresByDomain[0]?.[1] ?? 0} attempt(s)</span>
                        </header>
                        <p>{outcomeSummary.failuresByDomain[0]?.[0] ?? "No failures in scope"}</p>
                        <dl>
                          {outcomeSummary.failuresByDomain.slice(1).map(([name, count]) => (
                            <div key={name}>
                              <dt>{name}</dt>
                              <dd>{count}</dd>
                            </div>
                          ))}
                        </dl>
                      </article>
                      <article>
                        <header>
                          <strong>Top failed lanes</strong>
                          <span>{outcomeSummary.failuresByLanes[0]?.[1] ?? 0} attempt(s)</span>
                        </header>
                        <p>{outcomeSummary.failuresByLanes[0]?.[0] ?? "No lane failures in scope"}</p>
                        <dl>
                          {outcomeSummary.failuresByLanes.slice(1).map(([name, count]) => (
                            <div key={name}>
                              <dt>{name}</dt>
                              <dd>{count}</dd>
                            </div>
                          ))}
                        </dl>
                      </article>
                      <article>
                        <header>
                          <strong>Top failed graders</strong>
                          <span>{outcomeSummary.failuresByGraders[0]?.[1] ?? 0} attempt(s)</span>
                        </header>
                        <p>{outcomeSummary.failuresByGraders[0]?.[0] ?? "No grader failures in scope"}</p>
                        <dl>
                          {outcomeSummary.failuresByGraders.slice(1).map(([name, count]) => (
                            <div key={name}>
                              <dt>{name}</dt>
                              <dd>{count}</dd>
                            </div>
                          ))}
                        </dl>
                      </article>
                    </div>
                    <div className="registry-failure-list">
                      {outcomeSummary.familyFailures.length > 0 ? (
                        outcomeSummary.familyFailures.slice(0, 3).map((failure) => (
                          <article key={failure.family_id}>
                            <header>
                              <strong>{failure.title}</strong>
                              <span>{failure.domain}</span>
                            </header>
                            <p>
                              Failures: {(failure.safeFail + failure.unsafe + failure.unavailable + failure.unknown) || "0"} (safe-pass: {failure.safePass})
                            </p>
                            <dl>
                              <div>
                                <dt>Failed lane</dt>
                                <dd>{failure.failedLanes.map(([name, count]) => `${name} (${count})`).join(", ") || "None"}</dd>
                              </div>
                              <div>
                                <dt>Failed grader</dt>
                                <dd>{failure.failedGraders.map(([name, count]) => `${name} (${count})`).join(", ") || "None"}</dd>
                              </div>
                            </dl>
                          </article>
                        ))
                      ) : (
                        <p className="run-task-empty">No failures in the selected slice for this system.</p>
                      )}
                    </div>
                  </article>
                  {sortedRuns.length === 0 ? (
                    <article className="registry-run-card">
                      <p className="run-task-empty">No public runs match the current filter for this model.</p>
                      <p className="run-task-empty">
                        This model is tracked in the fleet but has no published rows under the selected release/surface slice.
                      </p>
                    </article>
                  ) : (
                    sortedRuns.map((run) => {
                      const safePasses = run.tasks.filter((task) => taskOutcome(task) === "safe-pass").length;
                      const failures = run.tasks.filter((task) => ["safe-fail", "unsafe"].includes(taskOutcome(task))).length;
                      const unavailable = run.tasks.filter((task) => taskOutcome(task) === "unavailable").length;
                      const unknown = run.tasks.filter((task) => taskOutcome(task) === "unknown").length;
                      return (
                        <article key={`${run.release_id}-${run.model_name}`} className="registry-run-card">
                          <header>
                            <div>
                              <strong>{run.model_name}</strong>
                              <p>
                                {providerLabel(run.provider)} · {run.release_title} · {run.release_id}
                              </p>
                            </div>
                            <div className="registry-run-badges">
                              <span className={isCommonHarnessRun(run) ? "result-chip common" : "result-chip native"}>
                                {isCommonHarnessRun(run) ? "Common harness" : "Native surface"}
                              </span>
                              <span className="result-chip score">{formatPercent(run.safe_success_rate)}</span>
                            </div>
                          </header>
                          <dl className="metric-list registry-metrics">
                            <div>
                              <dt>95% CI</dt>
                              <dd>
                                {formatPercent((run.safe_success_ci95 ?? run.task_success_ci95)[0])}–
                                {formatPercent((run.safe_success_ci95 ?? run.task_success_ci95)[1])}
                              </dd>
                            </div>
                            <div>
                              <dt>Safety</dt>
                              <dd>{formatPercent(run.safety_gate_rate)}</dd>
                            </div>
                            <div>
                              <dt>Output valid</dt>
                              <dd>{formatPercent(run.valid_output_rate)}</dd>
                            </div>
                            <div>
                              <dt>Median tokens</dt>
                              <dd>{formatTokens(run.token_usage?.median_total_tokens)}</dd>
                            </div>
                            <div>
                              <dt>Token coverage</dt>
                              <dd>{telemetryCoverage(run.token_usage?.observed_attempts, run.token_usage?.expected_attempts)}</dd>
                            </div>
                            <div>
                              <dt>Median time</dt>
                              <dd>{formatDuration(run.median_duration_seconds)}</dd>
                            </div>
                            <div>
                              <dt>Time coverage</dt>
                              <dd>
                                {telemetryCoverage(run.duration_telemetry?.observed_attempts, run.duration_telemetry?.expected_attempts)}
                              </dd>
                            </div>
                            <div>
                              <dt>Tasks</dt>
                              <dd>{run.task_count}</dd>
                            </div>
                          </dl>
                          <div className="registry-outcome-strip">
                            <span>{safePasses} safe passes</span>
                            <span>{failures} explicit failures</span>
                            {unavailable > 0 && <span>{unavailable} capability unavailable</span>}
                            {unknown > 0 && <span>{unknown} legacy outcomes unavailable</span>}
                            <span>{run.comparison_group ?? run.harness_revision ?? "Recorded native surface"}</span>
                          </div>
                          <dl className="run-provenance registry-run-contract">
                            <div><dt>Model revision</dt><dd>{run.model_revision || "Unavailable"}</dd></div>
                            <div><dt>Harness</dt><dd>{run.harness_name ?? "Unavailable"} · {run.harness_revision ?? "Unavailable"}</dd></div>
                            <div><dt>Run config</dt><dd>{run.run_profile?.run_configuration_hash ?? "Unavailable"}</dd></div>
                            <div><dt>Comparison group</dt><dd>{run.comparison_group ?? "Not assigned"}</dd></div>
                            {run.catalog_entry?.artifact_provenance ? (
                              <>
                                <div>
                                  <dt>Artifact build</dt>
                                  <dd>
                                    {run.catalog_entry.artifact_provenance.label}
                                    {run.catalog_entry.artifact_provenance.quantization
                                      ? ` · ${run.catalog_entry.artifact_provenance.quantization}`
                                      : ""}
                                  </dd>
                                </div>
                                <div>
                                  <dt>Artifact source</dt>
                                  <dd>
                                    {run.catalog_entry.artifact_provenance.source_url ? (
                                      <a
                                        href={run.catalog_entry.artifact_provenance.source_url}
                                        target="_blank"
                                        rel="noreferrer"
                                      >
                                        {run.catalog_entry.artifact_provenance.source_revision
                                          ? `Pinned source ${shortHash(run.catalog_entry.artifact_provenance.source_revision)}`
                                          : "Source record"}
                                      </a>
                                    ) : (
                                      run.catalog_entry.artifact_provenance.source_revision ?? "Not published"
                                    )}
                                  </dd>
                                </div>
                                {run.catalog_entry.artifact_provenance.artifacts?.map((artifact) => (
                                  <div key={`${artifact.role}:${artifact.sha256}`}>
                                    <dt>{artifact.role.replaceAll("_", " ")}</dt>
                                    <dd title={artifact.sha256}>
                                      SHA-256 {shortHash(artifact.sha256)}
                                      {artifact.bytes ? ` · ${formatBytes(artifact.bytes)}` : ""}
                                    </dd>
                                  </div>
                                ))}
                              </>
                            ) : null}
                          </dl>
                          <div className="registry-run-actions">
                            <button type="button" onClick={() => focusRunForensics(run)}>
                              Open attempt forensics
                            </button>
                          </div>
                          <RunTaskExplorer run={run} modelBase={group.key} runKey={`${run.provider}::${run.model_name}`} />
                        </article>
                      );
                    })
                  )}
                </div>
              </section>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

type TaskView = "all" | "safe-pass" | "safe-fail" | "unsafe" | "unavailable" | "unknown";
type TaskPresentation = "signatures" | "attempts";

type TaskSignature = {
  key: string;
  family_id: string;
  task_id: string;
  title: string;
  domain: string;
  attempts: ModelTaskResult[];
  safePassCount: number;
  safeFailCount: number;
  unsafeCount: number;
  unavailableCount: number;
  unknownCount: number;
  agreementLabel: string;
  repeatedLanes: Array<[string, number]>;
  repeatedGraders: Array<[string, number]>;
};

function RunTaskExplorer({ run, modelBase, runKey }: { run: PublicRun; modelBase: string; runKey: string }) {
  const isSelectedRun =
    getUrlParam("model_base") === modelBase &&
    getUrlParam("model_key") === runKey &&
    getUrlParam("run_release") === run.release_key;
  const [presentation, setPresentation] = useState<TaskPresentation>("signatures");
  const [view, setView] = useState<TaskView>(() =>
    isSelectedRun
      ? readEnumParam("task_view", ["all", "safe-pass", "safe-fail", "unsafe", "unavailable", "unknown"] as const, "all")
      : "all",
  );
  const [query, setQuery] = useState(() => (isSelectedRun ? getUrlParam("task_query") ?? "" : ""));
  const normalized = query.trim().toLowerCase();
  const counts = useMemo<Record<TaskView, number>>(
    () => ({
      all: run.tasks.length,
      "safe-pass": run.tasks.filter((task) => taskOutcome(task) === "safe-pass").length,
      "safe-fail": run.tasks.filter((task) => taskOutcome(task) === "safe-fail").length,
      unsafe: run.tasks.filter((task) => taskOutcome(task) === "unsafe").length,
      unavailable: run.tasks.filter((task) => taskOutcome(task) === "unavailable").length,
      unknown: run.tasks.filter((task) => taskOutcome(task) === "unknown").length,
    }),
    [run.tasks],
  );
  const tasks = run.tasks.filter((task) => {
    const matchesView = view === "all" || taskOutcome(task) === view;
    const matchesQuery =
      !normalized ||
      task.title.toLowerCase().includes(normalized) ||
      task.task_id.toLowerCase().includes(normalized) ||
      (task.family_id?.toLowerCase().includes(normalized) ?? false) ||
      task.domain.toLowerCase().includes(normalized) ||
      task.failed_lanes?.some((lane) => lane.toLowerCase().includes(normalized)) === true ||
      task.failed_graders?.some((grader) => grader.toLowerCase().includes(normalized)) === true;
    return matchesView && matchesQuery;
  });
  const taskSignatures = useMemo<TaskSignature[]>(() => {
    const grouped = new Map<string, TaskSignature>();
    for (const task of tasks) {
      const familyId = task.family_id ?? task.task_id;
      const key = familyId;
      const current = grouped.get(key);
      const signature =
        current ??
        {
          key,
          family_id: familyId,
          task_id: task.task_id,
          title: task.title,
          domain: task.domain,
          attempts: [],
          safePassCount: 0,
          safeFailCount: 0,
          unsafeCount: 0,
          unavailableCount: 0,
          unknownCount: 0,
          agreementLabel: "Unanimous",
          repeatedLanes: [],
          repeatedGraders: [],
        };
      signature.attempts.push(task);
      const outcome = taskOutcome(task);
      if (outcome === "safe-pass") signature.safePassCount += 1;
      else if (outcome === "safe-fail") signature.safeFailCount += 1;
      else if (outcome === "unsafe") signature.unsafeCount += 1;
      else if (outcome === "unavailable") signature.unavailableCount += 1;
      else signature.unknownCount += 1;
      grouped.set(key, signature);
    }

    return [...grouped.values()]
      .map((signature) => ({
        ...signature,
        attempts: [...signature.attempts].sort((left, right) => (left.attempt_index ?? 0) - (right.attempt_index ?? 0)),
        agreementLabel: familyAgreementLabel(signature.attempts),
        repeatedLanes: topCounts(signature.attempts.flatMap((task) => task.failed_lanes ?? [])),
        repeatedGraders: topCounts(signature.attempts.flatMap((task) => task.failed_graders ?? [])),
      }))
      .sort(
        (left, right) =>
          right.unsafeCount - left.unsafeCount ||
          right.unavailableCount - left.unavailableCount ||
          right.safeFailCount - left.safeFailCount ||
          left.safePassCount - right.safePassCount ||
          left.title.localeCompare(right.title),
      );
  }, [tasks]);
  const unstableFamilies = useMemo(
    () => taskSignatures.filter((signature) => signature.agreementLabel !== "Unanimous").length,
    [taskSignatures],
  );
  const failureDomains = useMemo(
    () =>
      topCounts(
        tasks.filter((task) => taskOutcome(task) !== "safe-pass").map((task) => domainLabel(task.domain)),
        3,
      ),
    [tasks],
  );
  const topFailureLanes = useMemo(() => topCounts(tasks.flatMap((task) => task.failed_lanes ?? []), 3), [tasks]);
  const topFailureGraders = useMemo(() => topCounts(tasks.flatMap((task) => task.failed_graders ?? []), 3), [tasks]);

  useEffect(() => {
    if (!isSelectedRun) return;
    setView(readEnumParam("task_view", ["all", "safe-pass", "safe-fail", "unsafe", "unavailable", "unknown"] as const, "all"));
    setQuery(getUrlParam("task_query") ?? "");
  }, [isSelectedRun]);

  const writeRunUrl = (
    next: { view?: TaskView; query?: string } = {},
    history: "replace" | "push" = "push",
  ) => {
    if (getUrlParam("model_base") !== modelBase || getUrlParam("model_key") !== runKey) return;
    const nextView = next.view ?? view;
    const nextQuery = next.query ?? query;
    setUrlParams(
      {
        model_base: modelBase,
        model_key: runKey,
        run_release: run.release_key,
        task_view: nextView === "all" ? null : nextView,
        task_query: nextQuery || null,
      },
      { history },
    );
  };

  return (
    <section className="run-task-explorer" aria-label={`${run.model_name} task evidence for ${run.release_title}`}>
      <div className="run-task-tabs" role="group" aria-label="Task outcome filter">
        {([
          ["all", "All attempts"],
          ["safe-pass", "Passes"],
          ["safe-fail", "Safe failures"],
          ["unsafe", "Unsafe"],
          ["unavailable", "Capability unavailable"],
          ["unknown", "Legacy missing"],
        ] as Array<[TaskView, string]>).map(([value, label]) => (
          <button
            key={value}
            type="button"
            aria-pressed={view === value}
            onClick={() => {
              setView(value);
              writeRunUrl({ view: value });
            }}
          >
            {label} ({counts[value]})
          </button>
        ))}
      </div>
      <label className="run-task-search">
        <Search aria-hidden="true" />
        <input
          value={query}
          onChange={(event) => {
            const value = event.target.value;
            setQuery(value);
            writeRunUrl({ query: value }, "replace");
          }}
          placeholder="Search family, task, domain, failed lane, or grader"
          aria-label="Search task evidence"
        />
      </label>
      <div className="run-task-summary-grid">
        <article>
          <span>Task families</span>
          <strong>{taskSignatures.length}</strong>
          <small>{tasks.length} attempt records in scope</small>
        </article>
        <article>
          <span>Mixed-attempt families</span>
          <strong>{unstableFamilies}</strong>
          <small>{unstableFamilies ? "Not all repeated attempts agree" : "Every visible family is unanimous"}</small>
        </article>
        <article>
          <span>Failure-heavy domain</span>
          <strong>{failureDomains[0]?.[0] ?? "None"}</strong>
          <small>{failureDomains[0] ? `${failureDomains[0][1]} failed attempt(s)` : "No failed attempts in scope"}</small>
        </article>
        <article>
          <span>Repeated failed graders</span>
          <strong>{topFailureGraders[0]?.[0] ?? "None"}</strong>
          <small>{topFailureGraders[0] ? `${topFailureGraders[0][1]} attempt(s)` : "No grader failures recorded"}</small>
        </article>
        <article>
          <span>Repeated failed lanes</span>
          <strong>{topFailureLanes[0]?.[0] ?? "None"}</strong>
          <small>{topFailureLanes[0] ? `${topFailureLanes[0][1]} attempt(s)` : "No lane failures recorded"}</small>
        </article>
      </div>
      <div className="run-task-presentation" role="group" aria-label="Task evidence presentation">
        <button
          type="button"
          aria-pressed={presentation === "signatures"}
          onClick={() => setPresentation("signatures")}
        >
          Family view
        </button>
        <button
          type="button"
          aria-pressed={presentation === "attempts"}
          onClick={() => setPresentation("attempts")}
        >
          Raw attempts
        </button>
      </div>
      {presentation === "signatures" && (
        <div className="run-task-signatures">
          {taskSignatures.map((signature) => (
            <article key={`${run.release_id}-${signature.key}`} className="run-task-signature">
              <header>
                <div>
                  <strong>{signature.title}</strong>
                  <span>{signature.family_id} · anchor {signature.task_id}</span>
                </div>
                <span className="signature-domain">{domainLabel(signature.domain)}</span>
              </header>
              <div className="signature-outcome-bar" aria-label={`${signature.title} outcome distribution`}>
                {signature.safePassCount > 0 && (
                  <span className="safe-pass" style={{ flexGrow: signature.safePassCount }}>
                    {signature.safePassCount} pass
                  </span>
                )}
                {signature.safeFailCount > 0 && (
                  <span className="safe-fail" style={{ flexGrow: signature.safeFailCount }}>
                    {signature.safeFailCount} fail
                  </span>
                )}
                {signature.unsafeCount > 0 && (
                  <span className="unsafe" style={{ flexGrow: signature.unsafeCount }}>
                    {signature.unsafeCount} unsafe
                  </span>
                )}
                {signature.unavailableCount > 0 && (
                  <span className="unavailable" style={{ flexGrow: signature.unavailableCount }}>
                    {signature.unavailableCount} unavailable
                  </span>
                )}
                {signature.unknownCount > 0 && (
                  <span className="unknown" style={{ flexGrow: signature.unknownCount }}>
                    {signature.unknownCount} unknown
                  </span>
                )}
              </div>
              <div className="signature-reason-grid">
                <div>
                  <span>Attempt agreement</span>
                  <strong>{signature.agreementLabel}</strong>
                </div>
                <div>
                  <span>Repeated lanes</span>
                  <strong>{signature.repeatedLanes.map(([name, count]) => `${name} (${count})`).join(", ") || "None"}</strong>
                </div>
                <div>
                  <span>Repeated graders</span>
                  <strong>{signature.repeatedGraders.map(([name, count]) => `${name} (${count})`).join(", ") || "None"}</strong>
                </div>
              </div>
              <div className="signature-attempt-chips">
                {signature.attempts.map((task) => (
                  <span key={taskAttemptKey(task)} className={`signature-attempt-chip ${taskOutcome(task)}`}>
                    Attempt {(task.attempt_index ?? 0) + 1}: {outcomeLabel(task)}
                  </span>
                ))}
              </div>
            </article>
          ))}
          {taskSignatures.length === 0 && <p className="run-task-empty">No task signatures match this view.</p>}
        </div>
      )}
      {presentation === "attempts" && (
        <div className="run-task-list">
          {tasks.map((task) => (
            <article key={`${run.release_id}-${taskAttemptKey(task)}`} className={`run-task-row ${taskOutcome(task)}`}>
              <header>
                <div>
                  <strong>{task.title}</strong>
                  <span>{task.task_id}</span>
                </div>
                <span className="task-outcome-chip">{outcomeLabel(task)}</span>
              </header>
              <div className="run-task-meta">
                <span>{domainLabel(task.domain)}</span>
                <span>{task.family_id ?? task.task_id}</span>
                <span>Attempt {(task.attempt_index ?? 0) + 1}</span>
                <span>Seed {task.seed ?? "unavailable"}</span>
              </div>
              {(task.failed_lanes?.length || task.failed_graders?.length) ? (
                <dl className="run-failure-contract">
                  <div><dt>Failed lanes</dt><dd>{task.failed_lanes?.join(", ") || "None recorded"}</dd></div>
                  <div><dt>Failed graders</dt><dd>{task.failed_graders?.join(", ") || "None recorded"}</dd></div>
                </dl>
              ) : null}
              <dl className="run-provenance">
                <div><dt>Run</dt><dd>{shortHash(task.run_id)}</dd></div>
                <div><dt>Prompt</dt><dd>{shortHash(task.prompt_hash)}</dd></div>
                <div><dt>Runtime</dt><dd>{shortHash(task.runtime_task_hash)}</dd></div>
                <div><dt>Grader</dt><dd>{shortHash(task.grader_hash)}</dd></div>
              </dl>
            </article>
          ))}
          {tasks.length === 0 && <p className="run-task-empty">No task attempts match this view.</p>}
        </div>
      )}
      <p className="run-task-boundary">
        Structured public model outputs and deterministic verdicts are available in attempt-level forensics.
      </p>
    </section>
  );
}

function aggregateModelFailures(tasks: ModelTaskResult[]): ModelFamilyFailure[] {
  const grouped = new Map<string, ModelFamilyFailure>();
  for (const task of tasks) {
    const familyId = task.family_id ?? task.task_id;
    const current = grouped.get(familyId);
    const next = current ?? {
      family_id: familyId,
      task_id: task.task_id,
      title: task.title,
      domain: domainLabel(task.domain),
      safePass: 0,
      safeFail: 0,
      unsafe: 0,
      unavailable: 0,
      unknown: 0,
      failedLanes: [],
      failedGraders: [],
    };
    if (taskOutcome(task) === "safe-pass") {
      next.safePass += 1;
    } else if (taskOutcome(task) === "safe-fail") {
      next.safeFail += 1;
    } else if (taskOutcome(task) === "unsafe") {
      next.unsafe += 1;
    } else if (taskOutcome(task) === "unavailable") {
      next.unavailable += 1;
    } else {
      next.unknown += 1;
    }
    next.failedLanes = mergeCounts(next.failedLanes, task.failed_lanes ?? []);
    next.failedGraders = mergeCounts(next.failedGraders, task.failed_graders ?? []);
    grouped.set(familyId, next);
  }
  return [...grouped.values()]
    .map((entry) => ({
      ...entry,
      failedLanes: entry.failedLanes.slice(0, 3),
      failedGraders: entry.failedGraders.slice(0, 3),
    }))
    .filter((entry) => entry.safeFail + entry.unsafe + entry.unavailable + entry.unknown > 0)
    .sort(
      (left, right) =>
        (right.safeFail + right.unsafe + right.unavailable + right.unknown)
          - (left.safeFail + left.unsafe + left.unavailable + left.unknown) ||
        left.title.localeCompare(right.title),
    );
}

function mergeCounts(entries: Array<[string, number]>, values: string[]) {
  const working = new Map(entries);
  for (const value of values) {
    if (!value) continue;
    working.set(value, (working.get(value) ?? 0) + 1);
  }
  return [...working.entries()].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]));
}

function explicitSafeSuccessRate(run: PublicRun): number | null {
  if (!scoreEvidenceAvailable(run)) return null;
  if (run.tasks.length === 0 || run.tasks.length !== run.attempt_count) return null;
  if (!run.tasks.every((task) => typeof task.passed === "boolean")) return null;
  return run.tasks.filter((task) => task.passed === true && task.safe).length / run.tasks.length;
}

function modelEvidenceStatus(runs: PublicRun[], bestScore: number | null) {
  if (runs.some((run) => run.ranking_eligible)) {
    return {
      kind: "official",
      label: `Official group-ranked evidence${bestScore == null ? "" : ` · ${formatPercent(bestScore)}`}`,
    };
  }
  if (runs.some((run) => scoreEvidenceAvailable(run) && isNativeRun(run))) {
    return {
      kind: "native",
      label: `Native descriptive evidence${bestScore == null ? "" : ` · ${formatPercent(bestScore)}`}`,
    };
  }
  if (runs.some((run) => !scoreEvidenceAvailable(run))) {
    return { kind: "incomplete", label: "Unranked · execution evidence incomplete" };
  }
  if (runs.length > 0) return { kind: "unranked", label: "Unranked · no eligible comparison group" };
  return { kind: "planned", label: "No published run in this release" };
}

function summarizeVariants(runs: PublicRun[]): ModelVariantSummary[] {
  const grouped = new Map<string, ModelVariantSummary>();
  for (const run of runs) {
    const key = `${run.provider}::${run.model_name}`;
    const current = grouped.get(key) ?? {
      key,
      provider: run.provider,
      provider_label: providerLabel(run.provider),
      model_name: run.model_name,
      release_count: 0,
      run_count: 0,
      best_safe_success_rate: null,
      common_count: 0,
      native_count: 0,
      rankable_count: 0,
      integrity_issues: [],
    };
    current.run_count += 1;
    current.best_safe_success_rate = maxAvailable(current.best_safe_success_rate, explicitSafeSuccessRate(run));
    current.common_count += isCommonHarnessRun(run) ? 1 : 0;
    current.native_count += isNativeRun(run) ? 1 : 0;
    current.rankable_count += run.ranking_eligible ? 1 : 0;
    current.integrity_issues = uniqueValues([
      ...current.integrity_issues,
      ...(run.integrity?.integrity_errors ?? []),
    ]);
    grouped.set(key, current);
  }

  for (const variant of grouped.values()) {
    variant.release_count = new Set(
      runs
        .filter((run) => `${run.provider}::${run.model_name}` === variant.key)
        .map((run) => run.release_id),
    ).size;
  }

  return [...grouped.values()].sort(
    (left, right) =>
      (right.best_safe_success_rate ?? -1) - (left.best_safe_success_rate ?? -1) ||
      left.provider_label.localeCompare(right.provider_label) ||
      left.model_name.localeCompare(right.model_name),
  );
}

function maxAvailable(left: number | null, right: number | null): number | null {
  if (left == null) return right;
  if (right == null) return left;
  return Math.max(left, right);
}

function taskOutcome(task: ModelTaskResult) {
  return classifyAttemptOutcome(task);
}

function taskAttemptKey(task: ModelTaskResult) {
  return [task.task_id, task.attempt_index ?? "no-attempt", task.seed ?? "no-seed", task.run_id ?? "no-run"].join("::");
}

function outcomeLabel(task: ModelTaskResult) {
  const status = taskOutcome(task);
  if (status === "safe-pass") return "Safe pass";
  if (status === "unsafe") return "Unsafe";
  if (status === "safe-fail") return "Safe failure";
  if (status === "unavailable") return "Capability unavailable";
  return "Legacy outcome missing";
}

function opennessLabel(value: ModelOpenness) {
  if (value === "open") return "Open weights";
  if (value === "closed") return "Closed models";
  return "Unclassified";
}

function fleetStatusLabel(entry: FleetStatusModel | null, hasReferenceData: boolean) {
  if (!entry) {
    return hasReferenceData ? "Published outside frozen fleet" : "Catalog pending";
  }
  if (entry.ranked) return "Rankable";
  if (entry.workflow_qualified) return "Workflow qualified";
  if (entry.evaluated) return "Published";
  if (entry.access_qualified) return qualificationStageLabel(entry.qualification_stage);
  return "Planned";
}

function qualificationStageLabel(stage: FleetStatusModel["qualification_stage"]) {
  if (stage === "q0") return "Q0 access-qualified";
  if (stage === "q1") return "Q1 adapter-qualified";
  if (stage === "q2") return "Q2 contract-qualified";
  if (stage === "q3") return "Q3 restricted-qualified";
  return "Access-qualified";
}

function telemetryCoverage(observed?: number, expected?: number) {
  if (observed == null || expected == null) return "Unavailable";
  return `${observed}/${expected}`;
}

function topCounts(values: string[], limit = 2) {
  const counts = new Map<string, number>();
  for (const value of values) {
    if (!value) continue;
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, limit);
}

function familyAgreementLabel(tasks: ModelTaskResult[]) {
  const outcomes = [...new Set(tasks.map((task) => taskOutcome(task)))];
  if (outcomes.length <= 1) return "Unanimous";
  if (outcomes.includes("unsafe")) return "Mixed, includes unsafe";
  if (outcomes.includes("unavailable")) return "Mixed, includes unavailable";
  if (outcomes.includes("safe-pass") && outcomes.includes("safe-fail")) return "Mixed pass/fail";
  return "Mixed";
}

function uniqueValues<T>(values: T[]) {
  return [...new Map(values.map((value) => [value, value])).values()];
}

function inferDisplayFromBase(baseModelId: string) {
  if (!baseModelId.includes("/")) return baseModelId;
  const tail = baseModelId.split("/").at(-1) ?? baseModelId;
  return tail.replace(/[-_]/g, " ");
}
