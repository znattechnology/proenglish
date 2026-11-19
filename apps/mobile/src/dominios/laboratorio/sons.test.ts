// Regras de quando tocam os sons e fala a Luena. Correr: npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { FRASES_LUENA, somDoMomento, type Contagem } from "./sons.ts";

const c = (certos: number, seguidos: number, errados = 0): Contagem => ({ certos, seguidos, errados });

test("cada resposta tem o seu toque", () => {
  assert.equal(somDoMomento({ tipo: "certo", falado: false }, c(2, 2)).toque, "certo");
  assert.equal(somDoMomento({ tipo: "errado", falado: false }, c(0, 0, 2)).toque, "errado");
});

test("a Luena fala no 1.º certo e depois de 4 em 4, não em todos", () => {
  const falas = [1, 2, 4, 5, 6, 9].map((n) => somDoMomento({ tipo: "certo", falado: false }, c(n, 1)).fala);
  assert.deepEqual(falas.map(Boolean), [true, false, false, true, false, true]);
  // e varia a frase
  assert.notEqual(falas[0], falas[3]);
});

test("sequências de 3 e 5 têm toque e frase próprios", () => {
  assert.deepEqual(somDoMomento({ tipo: "certo", falado: false }, c(3, 3)), { toque: "sequencia", fala: "seguidas-3" });
  assert.deepEqual(somDoMomento({ tipo: "certo", falado: false }, c(7, 5)), { toque: "sequencia", fala: "seguidas-5" });
  assert.equal(somDoMomento({ tipo: "certo", falado: false }, c(6, 4)).toque, "certo");
});

test("pronúncia aceite e gravação recusada têm frases próprias", () => {
  assert.equal(somDoMomento({ tipo: "certo", falado: true }, c(1, 1)).fala, "pronuncia-certo");
  assert.equal(somDoMomento({ tipo: "errado", falado: true }, c(0, 0, 1)).fala, "fala-errado");
});

test("erros: fala no 1.º e depois de 3 em 3", () => {
  const falas = [1, 2, 3, 4, 7].map((n) => somDoMomento({ tipo: "errado", falado: false }, c(0, 0, n)).fala);
  assert.deepEqual(falas.map(Boolean), [true, false, false, true, true]);
});

test("sem vidas e fim da lição falam sempre; a meta tem prioridade", () => {
  assert.deepEqual(somDoMomento({ tipo: "sem-vidas" }, c(0, 0, 3)), { toque: "sem-vidas", fala: "sem-vidas" });
  assert.deepEqual(somDoMomento({ tipo: "concluida", meta: true }, c(5, 2)), { toque: "meta", fala: "meta" });
  assert.equal(somDoMomento({ tipo: "concluida", meta: false }, c(5, 2)).toque, "concluida");
});

test("todas as frases escolhidas existem", () => {
  for (let n = 0; n < 30; n++) {
    for (const m of [{ tipo: "certo", falado: false }, { tipo: "certo", falado: true }, { tipo: "errado", falado: false }, { tipo: "concluida", meta: false }] as const) {
      const f = somDoMomento(m, c(n, n % 7, n)).fala;
      if (f) assert.ok(f in FRASES_LUENA, f);
    }
  }
});
