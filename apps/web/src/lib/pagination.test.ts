import { describe, expect, it } from "vitest";

import { lastPage, pageOffset, pageWindow, parsePage, totalCount } from "./pagination";

describe("parsePage", () => {
  it.each([
    [undefined, 1],
    ["", 1],
    ["abc", 1],
    ["0", 1],
    ["-3", 1],
    ["2.5", 1],
    ["1", 1],
    ["7", 7],
  ])("%j -> page %i", (raw, expected) => {
    expect(parsePage(raw as string | undefined)).toBe(expected);
  });
});

describe("totalCount", () => {
  const response = (value: string | null) => ({ headers: { get: () => value } });

  it("lit le total du serveur", () => {
    expect(totalCount(response("230"))).toBe(230);
  });

  it("un total absent n'est jamais confondu avec zéro", () => {
    expect(totalCount(response(null))).toBeNull();
  });

  it.each(["abc", "-1", "1.5"])("ignore un total invalide (%s)", (value) => {
    expect(totalCount(response(value))).toBeNull();
  });
});

describe("pageWindow", () => {
  it("décrit la première page", () => {
    expect(pageWindow({ page: 1, total: 230, returned: 50 })).toEqual({
      page: 1,
      totalPages: 5,
      from: 1,
      to: 50,
      total: 230,
      hasPrevious: false,
      hasNext: true,
    });
  });

  it("décrit une page intermédiaire et la dernière page, plus courte", () => {
    expect(pageWindow({ page: 3, total: 230, returned: 50 })).toMatchObject({ from: 101, to: 150 });
    expect(pageWindow({ page: 5, total: 230, returned: 30 })).toMatchObject({
      from: 201,
      to: 230,
      hasNext: false,
      hasPrevious: true,
    });
  });

  it("une liste vide n'annonce pas « 1 à 0 »", () => {
    expect(pageWindow({ page: 1, total: 0, returned: 0 })).toMatchObject({
      from: 0,
      to: 0,
      totalPages: 1,
      hasNext: false,
    });
  });

  it("un total exactement multiple de la taille de page n'ajoute pas de page vide", () => {
    expect(pageWindow({ page: 2, total: 100, returned: 50 })).toMatchObject({
      totalPages: 2,
      hasNext: false,
    });
  });
});

describe("pageOffset et lastPage", () => {
  it("calcule le décalage envoyé au serveur", () => {
    expect(pageOffset(1)).toBe(0);
    expect(pageOffset(3)).toBe(100);
  });

  it("ramène une adresse trop loin à la dernière page existante", () => {
    expect(lastPage(230)).toBe(5);
    expect(lastPage(0)).toBe(1);
  });
});
