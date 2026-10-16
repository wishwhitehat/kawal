/** Strip markdown bold (**text**) without touching masked values like +6011******89. */
export function plain(md: string): string {
  return md.replace(/(^|[\s(])\*\*([^*\n]+?)\*\*(?=[\s.,;:!?)]|$)/gm, "$1$2");
}
