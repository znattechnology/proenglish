"""
Interface comum dos fornecedores de avaliação de pronúncia.

Um fornecedor recebe a gravação (bytes + mime), o texto esperado e o modo ('lido' = o aluno lê ou
repete um texto conhecido; 'livre' = fala espontânea, sem texto) e devolve um ResultadoPronuncia.
Levanta ErroProvedor quando não consegue avaliar (o chamador recorre à avaliação pelo texto).

ResultadoPronuncia expõe também os nomes antigos (transcribed_text, overall_score, is_acceptable,
...) para os chamadores que já usavam o PronunciationResult de services/ai_pronunciation.py.
"""
from dataclasses import dataclass, field
from typing import List, Optional

MODOS = ('lido', 'livre')
NOTA_ACEITE = 60


class ErroProvedor(Exception):
    """O fornecedor não avaliou (configuração, rede, formato, limite): recorrer ao texto."""


def credito_de(nota):
    """Pontos (0-10) pela nota, com as faixas da avaliação pelo texto."""
    for minimo, pontos in ((90, 10), (80, 8), (70, 6), (60, 4), (50, 2)):
        if nota >= minimo:
            return pontos
    return 0


@dataclass
class ResultadoPronuncia:
    nota: int = 0                       # 0-100, geral
    fluencia: Optional[int] = None
    completude: Optional[int] = None
    prosodia: Optional[int] = None
    palavras: List[dict] = field(default_factory=list)  # [{palavra, nota, erro_tipo, fonemas:[{fonema, nota}]}]
    fonte: str = 'texto'                # 'texto' | 'azure' | 'simulada'
    transcricao: str = ''
    texto_esperado: str = ''
    aceite: bool = False
    mensagem: str = ''
    sugestoes: List[str] = field(default_factory=list)
    palavras_problematicas: List[str] = field(default_factory=list)
    nota_pronuncia: int = 0
    nota_clareza: int = 0
    credito: int = 0
    confianca: object = 0.5
    indisponivel: bool = False          # o serviço falhou: 503, pode saltar, não conta
    sem_fala: bool = False              # transcrição vazia: grava outra vez (422), não conta
    audio_invalido: bool = False        # o fornecedor recusou a gravação: grava outra vez (422), não conta
    tempos: object = None               # transcricao_fala.Transcricao (tempos das palavras), ou None
    detalhada: bool = False             # True quando há notas por palavra (palavras)

    # Nomes antigos (PronunciationResult)
    @property
    def transcribed_text(self):
        return self.transcricao

    @property
    def expected_text(self):
        return self.texto_esperado

    @property
    def pronunciation_score(self):
        return self.nota_pronuncia

    @property
    def fluency_score(self):
        return self.fluencia or 0

    @property
    def clarity_score(self):
        return self.nota_clareza

    @property
    def overall_score(self):
        return self.nota

    @property
    def is_acceptable(self):
        return self.aceite

    @property
    def feedback(self):
        return self.mensagem

    @property
    def problematic_words(self):
        return self.palavras_problematicas

    @property
    def suggestions(self):
        return self.sugestoes

    @property
    def partial_credit(self):
        return self.credito

    @property
    def confidence_level(self):
        return self.confianca

    @property
    def transcricao_fala(self):
        return self.tempos


class Provedor:
    nome = 'base'

    def avaliar(self, audio_bytes, mime, texto_esperado=None, idioma='en-US', modo='lido', nivel='intermediate'):
        raise NotImplementedError  # pragma: no cover
