// Aviso «pratique primeiro». Correr: node --experimental-strip-types --test components/pe/curso/praticaAnterior.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { chaveFechado, fechar, foiFechado, praticaAnterior, type PraticaAnterior } from "./praticaAnterior.ts";

const lab: PraticaAnterior = { aula_id: "a1", aula_titulo: "1A — Hello, I'm…", licao_id: "l1", curso_pratica_id: "c9", minutos: 8 };
const percurso = {
  unidades: [
    { aulas: [{ id: "a1", pratica_anterior: null }, { id: "a2", pratica_anterior: lab }] },
    { aulas: [{ id: "a3" }] },
  ],
};

test("devolve o laboratório por fazer da aula anterior, vindo do servidor", () => {
  assert.deepEqual(praticaAnterior(percurso, "a2"), lab);
});

test("sem aviso: primeira aula, campo em falta, aula desconhecida ou percurso por carregar", () => {
  assert.equal(praticaAnterior(percurso, "a1"), null);
  assert.equal(praticaAnterior(percurso, "a3"), null);
  assert.equal(praticaAnterior(percurso, "zz"), null);
  assert.equal(praticaAnterior(undefined, "a2"), null);
});

function memoria() {
  const m = new Map<string, string>();
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v) };
}

test("«Continuar esta aula» fecha o aviso só nesta aula e para esta lição", () => {
  const g = memoria();
  assert.equal(foiFechado(g, "a2", "l1"), false);
  fechar(g, "a2", "l1");
  assert.equal(foiFechado(g, "a2", "l1"), true);
  assert.equal(foiFechado(g, "a3", "l1"), false);
  assert.equal(foiFechado(g, "a2", "l2"), false);
  assert.equal(chaveFechado("a2", "l1"), "pe:pratica-anterior:a2:l1");
});

test("sem armazenamento (ou a falhar) não rebenta e o aviso aparece", () => {
  const avaria = {
    getItem: () => {
      throw new Error("bloqueado");
    },
    setItem: () => {
      throw new Error("bloqueado");
    },
  };
  assert.equal(foiFechado(avaria, "a2", "l1"), false);
  assert.doesNotThrow(() => fechar(avaria, "a2", "l1"));
  assert.equal(foiFechado(null, "a2", "l1"), false);
});
