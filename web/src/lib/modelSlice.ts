export function providerIdsForSlice(
  catalogProviders: readonly string[],
  runProviders: readonly string[],
  selectedProvider: string,
) {
  const available = [...new Set([...catalogProviders, ...runProviders])].sort((left, right) =>
    left.localeCompare(right),
  );
  if (selectedProvider === "all") return available;
  return available.includes(selectedProvider) ? [selectedProvider] : [];
}
