export const DATA_ASSET_REVISION = "2703def";

export function versionedDataUrl(path: string) {
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}release=${DATA_ASSET_REVISION}`;
}
