import en from "../../messages/en.json";

type Tree = { [key: string]: string | Tree };

export function t(key: string): string {
  const value = key.split(".").reduce<string | Tree | undefined>((node, part) => {
    if (node && typeof node === "object") return node[part];
    return undefined;
  }, en as Tree);
  return typeof value === "string" ? value : key;
}
