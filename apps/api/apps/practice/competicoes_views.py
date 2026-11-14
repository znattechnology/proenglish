"""
Aluno: certificado de mérito de uma competição (página HTML simples, para imprimir).

  GET /api/v1/practice/competicoes/<id>/certificado/

Só o próprio aluno premiado com certificado de mérito a abre; os outros recebem 404.
"""
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.utils.html import escape
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import StaticHTMLRenderer

from . import competicoes
from .models import Competition, CompetitionParticipant

MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro',
         'outubro', 'novembro', 'dezembro']


def _data(d):
    return f'{d.day} de {MESES[d.month - 1]} de {d.year}'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@renderer_classes([StaticHTMLRenderer])
def certificado(request, competicao_id):
    p = (CompetitionParticipant.objects.select_related('competition', 'competition__criado_por')
         .filter(competition_id=competicao_id, user=request.user,
                 premio=Competition.PREMIO_CERTIFICADO).first())
    if p is None:
        raise Http404('Certificado não encontrado.')
    c = p.competition
    professor = c.criado_por.name if c.criado_por_id else 'Equipa ProEnglish'
    unidade = competicoes.UNIDADE_CONTA[c.conta]
    html = f"""<!doctype html>
<html lang="pt-PT"><head><meta charset="utf-8"><title>Certificado de mérito</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  @page {{ size: A4 landscape; margin: 0; }}
  body {{ margin: 0; font-family: Georgia, 'Times New Roman', serif; background: #f4f1ea; color: #1d2a3a; }}
  .folha {{ max-width: 960px; margin: 24px auto; background: #fff; border: 10px double #1d2a3a;
           padding: 56px 48px; text-align: center; }}
  h1 {{ font-size: 40px; margin: 0 0 8px; letter-spacing: 1px; }}
  .sub {{ font-size: 16px; text-transform: uppercase; letter-spacing: 3px; color: #6b5b2e; }}
  .nome {{ font-size: 34px; margin: 32px 0 8px; border-bottom: 1px solid #ccc; display: inline-block;
          padding: 0 24px 8px; }}
  p {{ font-size: 18px; line-height: 1.6; }}
  .rodape {{ margin-top: 40px; display: flex; justify-content: space-between; font-size: 14px; color: #555; }}
  .imprimir {{ margin: 16px auto; display: block; padding: 10px 20px; font-size: 16px; cursor: pointer; }}
  @media print {{ .imprimir {{ display: none; }} body {{ background: #fff; }} .folha {{ margin: 0; }} }}
</style></head>
<body>
<button class="imprimir" onclick="window.print()">Imprimir</button>
<div class="folha">
  <div class="sub">ProEnglish</div>
  <h1>Certificado de mérito</h1>
  <p>Certificamos que</p>
  <div class="nome">{escape(request.user.name or request.user.email)}</div>
  <p>ficou em <strong>{p.current_rank}.º lugar</strong> na competição <strong>«{escape(c.title)}»</strong>,<br>
  com {p.valor} {escape(unidade)}, entre {_data(competicoes.dia_inicio(c))} e {_data(competicoes.dia_fim(c))}.</p>
  <div class="rodape"><span>{escape(professor)}</span><span>Emitido em {_data(timezone.localtime(c.fechada_em, competicoes.FUSO).date()) if c.fechada_em else ''}</span></div>
</div>
</body></html>"""
    return HttpResponse(html, content_type='text/html; charset=utf-8')
