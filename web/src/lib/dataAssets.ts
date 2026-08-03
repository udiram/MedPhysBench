export const DATA_ASSET_REVISION = "1425ce4";

export function versionedDataUrl(path: string) {
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}release=${DATA_ASSET_REVISION}`;
}
