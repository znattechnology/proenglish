// Aviso «pratique primeiro». Correr: node --experimental-strip-types --test src/dominios/cursos/praticaAnterior.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { chaveFechado, praticaAnterior, type PraticaAnterior } from "./praticaAnterior.ts";

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

test("a chave do «Continuar esta aula» é por aula e por lição", () => {
  assert.equal(chaveFechado("a2", "l1"), "pe:pratica-anterior:a2:l1");
  assert.notEqual(chaveFechado("a3", "l1"), chaveFechado("a2", "l1"));
});
