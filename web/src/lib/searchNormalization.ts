export function normalizeSearchText(value: string) {
  return value
    .normalize("NFKD")
    .toLowerCase()
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

export function matchesSearchText(candidate: string, query: string) {
  const normalizedQuery = normalizeSearchText(query);
  if (!normalizedQuery) return true;

  const normalizedCandidate = normalizeSearchText(candidate);
  if (normalizedCandidate.includes(normalizedQuery)) return true;

  return normalizedCandidate.replaceAll(" ", "").includes(normalizedQuery.replaceAll(" ", ""));
}
