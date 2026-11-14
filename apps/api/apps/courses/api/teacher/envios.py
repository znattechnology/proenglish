"""
Envio de ficheiros do editor de cursos em vídeo (um só fluxo para vídeo, materiais e capa).

1. O browser pede um envio, com {nome, tamanho_bytes, tipo_mime}:
     POST /api/v1/teacher/aulas/<id>/video/
     POST /api/v1/teacher/aulas/<id>/materiais/
     POST /api/v1/teacher/cursos/<id>/capa/
   O servidor valida o tipo e o tamanho e responde com
     {modo:"s3", upload_url, metodo:"PUT", cabecalhos:{Content-Type}, chave, expira_em}
   (USE_S3=True: URL pré-assinado para o bucket) ou
     {modo:"local", upload_url:"/api/v1/teacher/envios/<chave>/", metodo:"PUT", cabecalhos, chave, expira_em}
   (USE_S3=False: em desenvolvimento os bytes ficam em MEDIA_ROOT e nada vai para o bucket).
2. O browser envia os bytes para upload_url (PUT, corpo = o ficheiro).
3. O browser confirma: POST /api/v1/teacher/envios/confirmar/ {chave}
   -> grava o URL, o nome e o tamanho no destino e devolve a aula (vídeo), o material
      (materiais) ou o detalhe do curso (capa).

A `chave` é um valor assinado e de curta duração, ligado ao utilizador e ao destino; o servidor
não guarda nada até à confirmação. Cada chave só se confirma uma vez: depois disso o PUT local e
uma nova confirmação são recusados (409 envio_ja_confirmado).

O modo local só funciona em desenvolvimento (DEBUG, ou ENVIOS_LOCAIS=True); em produção sem S3
os pedidos de envio respondem 503.

Ficheiros substituídos ou apagados (vídeo, capa, fotografia, materiais, aulas e secções apagadas)
são apagados do armazenamento (local ou S3) depois do commit, se nenhum outro registo os usar.
"""
import hashlib
import logging
import os
import re
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.db import transaction
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.response import Response

from apps.courses.models import ChapterResource

from .cursos import PERMISSOES, _curso_do_professor, _erro
from .editor_video import (
    _aula_do_professor, _dados, _tocar, aula_dict, detalhe_com_acesso, material_dict,
)

logger = logging.getLogger(__name__)

SAL = 'teacher.envios'
DURACAO_CHAVE = 3 * 3600  # segundos (um vídeo de 2 GB pode demorar)
MB = 1024 * 1024
GB = 1024 * MB

# tipo_mime -> (extensões aceites, tipo do ChapterResource / pasta)
VIDEO = {
    'video/mp4': ('.mp4', '.m4v'),
    'video/webm': ('.webm',),
    'video/quicktime': ('.mov',),
}
MATERIAIS = {
    'application/pdf': (('.pdf',), 'PDF'),
    'audio/mpeg': (('.mp3',), 'AUDIO'),
    'audio/mp3': (('.mp3',), 'AUDIO'),
    'audio/mp4': (('.m4a',), 'AUDIO'),
    'audio/x-m4a': (('.m4a',), 'AUDIO'),
    'audio/m4a': (('.m4a',), 'AUDIO'),
    'audio/wav': (('.wav',), 'AUDIO'),
    'audio/x-wav': (('.wav',), 'AUDIO'),
    'audio/wave': (('.wav',), 'AUDIO'),
    'image/png': (('.png',), 'IMAGE'),
    'image/jpeg': (('.jpg', '.jpeg'), 'IMAGE'),
    'image/webp': (('.webp',), 'IMAGE'),
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': (('.xlsx',), 'WORKSHEET'),
    'text/csv': (('.csv',), 'WORKSHEET'),
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': (('.docx',), 'WORKSHEET'),
    'application/csv': (('.csv',), 'WORKSHEET'),
    'text/x-csv': (('.csv',), 'WORKSHEET'),
    'application/x-csv': (('.csv',), 'WORKSHEET'),
}
# Tipos genéricos que os browsers mandam para alguns ficheiros (CSV no Windows chega como
# application/vnd.ms-excel; .docx/.xlsx às vezes como zip ou octet-stream): decide a extensão.
MIME_GENERICOS = {'', 'application/octet-stream', 'application/vnd.ms-excel', 'application/zip',
                  'application/x-zip-compressed', 'text/plain', 'binary/octet-stream'}
MIME_POR_EXTENSAO = {
    '.pdf': 'application/pdf', '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4', '.wav': 'audio/wav',
    '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
    '.csv': 'text/csv',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}
CAPA = {
    'image/png': ('.png',),
    'image/jpeg': ('.jpg', '.jpeg'),
    'image/webp': ('.webp',),
}
PASTA_MATERIAL = {'PDF': 'documents', 'AUDIO': 'audio', 'IMAGE': 'images', 'WORKSHEET': 'worksheets'}

LIMITES = {'video': 2 * GB, 'material': 20 * MB, 'capa': 5 * MB, 'fotografia': 5 * MB}
TIPOS_TEXTO = {
    'video': 'MP4, WebM ou MOV',
    'material': 'PDF, MP3, M4A, WAV, PNG, JPG, WebP, XLSX, CSV ou DOCX',
    'capa': 'PNG, JPG ou WebP',
    'fotografia': 'PNG, JPG ou WebP',
}
LIMITES_TEXTO = {'video': '2 GB', 'material': '20 MB', 'capa': '5 MB', 'fotografia': '5 MB'}


# ---------------------------------------------------------------------------
# Ajudas
# ---------------------------------------------------------------------------

def usa_s3():
    return bool(getattr(settings, 'USE_S3', False))


def envios_locais_permitidos():
    """Guardar ficheiros no disco do servidor só em desenvolvimento (ou com ENVIOS_LOCAIS=True)."""
    return bool(getattr(settings, 'ENVIOS_LOCAIS', settings.DEBUG))


def _resposta_sem_armazenamento():
    return _erro('O envio de ficheiros não está disponível neste servidor (armazenamento não configurado). '
                 'Tente mais tarde ou contacte o suporte.', 'armazenamento_indisponivel', 503)


def nome_seguro(nome, extensao):
    """'Aula 1 — Introdução.MP4' -> 'Aula-1-Introducao.mp4' (só ASCII, curto, sem barras)."""
    import unicodedata
    base = os.path.splitext(os.path.basename(nome.replace('\\', '/')))[0]
    base = unicodedata.normalize('NFKD', base).encode('ascii', 'ignore').decode('ascii')
    base = re.sub(r'[^A-Za-z0-9._-]+', '-', base).strip('-._')[:60] or 'ficheiro'
    return f'{base}{extensao}'


def url_publico(chave_s3):
    dominio = getattr(settings, 'AWS_CLOUDFRONT_DOMAIN', '')
    if dominio:
        if not dominio.startswith('http'):
            dominio = f'https://{dominio}'
        return f'{dominio.rstrip("/")}/{chave_s3}'
    return f'https://{settings.AWS_S3_CUSTOM_DOMAIN}/{chave_s3}'


def _caminho_local(chave_ficheiro):
    raiz = Path(settings.MEDIA_ROOT).resolve()
    caminho = (raiz / chave_ficheiro).resolve()
    if raiz not in caminho.parents:
        raise ValueError('caminho fora de MEDIA_ROOT')
    return caminho


def url_local(request, chave_ficheiro):
    return request.build_absolute_uri(f'{settings.MEDIA_URL.rstrip("/")}/{chave_ficheiro}')


# Só se apagam ficheiros nas pastas para onde estes envios escrevem.
PASTAS_ENVIOS = ('videos/', 'chapter_resources/', 'courses/images/', 'avatars/')


def _bases_s3():
    bases = []
    dominio = getattr(settings, 'AWS_CLOUDFRONT_DOMAIN', '') or ''
    if dominio:
        if not dominio.startswith('http'):
            dominio = f'https://{dominio}'
        bases.append(dominio.rstrip('/') + '/')
    custom = getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', '') or ''
    if custom:
        bases.append(f'https://{custom.rstrip("/")}/')
    return bases


def _chave_s3_do_url(url):
    for base in _bases_s3():
        if url.startswith(base):
            chave = unquote(url[len(base):].split('?')[0])
            return chave if chave.startswith(PASTAS_ENVIOS) else None
    return None


def _em_uso(url):
    """Outro registo ainda aponta para este ficheiro?"""
    from apps.courses.models import Chapter, ChapterResource, Course
    from apps.users.models import User
    return (Chapter.objects.filter(video=url).exists()
            or Course.objects.filter(image=url).exists()
            or ChapterResource.objects.filter(external_url=url).exists()
            or User.objects.filter(avatar=url).exists())


def apagar_ficheiro(url):
    """
    Apaga o ficheiro de um URL que estes envios criaram (local em MEDIA_ROOT ou objecto no S3),
    se nenhum registo o usar. Nunca levanta excepções: falhas ficam no registo (log).
    """
    if not url or not isinstance(url, str):
        return False
    try:
        if _em_uso(url):
            return False
    except Exception:
        logger.exception('Não foi possível verificar se o ficheiro %s ainda é usado', url)
        return False
    chave = _chave_s3_do_url(url)
    if chave:
        bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '')
        if not (bucket and getattr(settings, 'AWS_ACCESS_KEY_ID', '') and getattr(settings, 'AWS_SECRET_ACCESS_KEY', '')):
            logger.warning('S3 sem credenciais: o objecto %s não foi apagado', chave)
            return False
        try:
            _s3().delete_object(Bucket=bucket, Key=chave)
            logger.info('Objecto apagado do S3: %s', chave)
            return True
        except Exception:
            logger.exception('Não foi possível apagar o objecto %s do S3', chave)
            return False
    caminho = unquote(urlparse(url).path)
    prefixo = settings.MEDIA_URL if settings.MEDIA_URL.startswith('/') else urlparse(settings.MEDIA_URL).path
    if not caminho.startswith(prefixo) or not caminho[len(prefixo):].startswith(PASTAS_ENVIOS):
        return False
    try:
        _caminho_local(caminho[len(prefixo):]).unlink(missing_ok=True)
        return True
    except (ValueError, OSError):
        logger.warning('Não foi possível apagar o ficheiro local %s', url)
        return False


# Nome antigo (usado por apps/users/professor.py): agora apaga também no S3.
apagar_ficheiro_local = apagar_ficheiro


def apagar_depois_do_commit(urls):
    """Agenda a remoção dos ficheiros para depois do commit (se a transacção falhar, ficam)."""
    urls = [u for u in dict.fromkeys(urls or []) if u]
    if urls:
        transaction.on_commit(lambda: [apagar_ficheiro(u) for u in urls])


def ficheiros_da_aula(aula):
    from apps.courses.models import ChapterResource
    urls = [aula.video]
    urls += list(ChapterResource.objects.filter(chapter=aula).values_list('external_url', flat=True))
    return [u for u in urls if u]


def _s3():
    import boto3
    return boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
    )


def _validar_pedido(dados, destino):
    """Devolve (erros, nome, tamanho, mime, extensao, tipo_material)."""
    erros = {}
    nome = dados.get('nome') if isinstance(dados.get('nome'), str) else ''
    nome = nome.strip()[:255]
    if not nome:
        erros['nome'] = ['Indique o nome do ficheiro.']
    tamanho = dados.get('tamanho_bytes')
    if isinstance(tamanho, bool) or not isinstance(tamanho, int) or tamanho <= 0:
        erros['tamanho_bytes'] = ['Indique o tamanho do ficheiro em bytes.']
        tamanho = None
    elif tamanho > LIMITES[destino]:
        erros['tamanho_bytes'] = [f'O ficheiro é demasiado grande. O máximo é {LIMITES_TEXTO[destino]}.']
    mime = dados.get('tipo_mime') if isinstance(dados.get('tipo_mime'), str) else ''
    mime = mime.strip().lower().split(';')[0]
    if destino == 'material' and mime in MIME_GENERICOS:
        mime = MIME_POR_EXTENSAO.get(os.path.splitext(nome)[1].lower(), mime)
    tabela = {'video': VIDEO, 'capa': CAPA, 'fotografia': CAPA}.get(destino)
    if destino == 'material':
        entrada = MATERIAIS.get(mime)
        extensoes, tipo_material = (entrada if entrada else ((), None))
    else:
        extensoes, tipo_material = tabela.get(mime, ()), None
    extensao = os.path.splitext(nome)[1].lower()
    if not extensoes:
        erros['tipo_mime'] = [f'Tipo de ficheiro não aceite. Use {TIPOS_TEXTO[destino]}.']
    elif extensao not in extensoes:
        extensao = extensoes[0]
    return erros, nome, tamanho, mime, extensao, tipo_material


def _iniciar(request, destino, alvo_id, curso_id):
    if not usa_s3() and not envios_locais_permitidos():
        return _resposta_sem_armazenamento()
    dados = _dados(request)
    erros, nome, tamanho, mime, extensao, tipo_material = _validar_pedido(dados, destino)
    if erros:
        primeiro = next(iter(erros.values()))[0]
        return _erro(primeiro, 'ficheiro_invalido', details=erros)

    unico = uuid.uuid4().hex
    if destino == 'video':
        chave_ficheiro = f'videos/{unico}/{nome_seguro(nome, extensao)}'
    elif destino == 'material':
        chave_ficheiro = f'chapter_resources/{PASTA_MATERIAL[tipo_material]}/{unico}/{nome_seguro(nome, extensao)}'
    elif destino == 'fotografia':
        chave_ficheiro = f'avatars/{unico}{extensao}'
    else:
        chave_ficheiro = f'courses/images/{unico}{extensao}'

    modo = 's3' if usa_s3() else 'local'
    chave = signing.dumps({
        'u': str(request.user.id), 'd': destino, 'a': str(alvo_id), 'c': str(curso_id), 'f': chave_ficheiro,
        'n': nome, 't': tamanho, 'm': mime, 'r': tipo_material, 'modo': modo,
    }, salt=SAL, compress=True)
    cabecalhos = {'Content-Type': mime}
    resposta = {'modo': modo, 'metodo': 'PUT', 'cabecalhos': cabecalhos, 'chave': chave,
                'expira_em_s': DURACAO_CHAVE}
    if modo == 's3':
        if not all([settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, settings.AWS_STORAGE_BUCKET_NAME]):
            return _erro('O armazenamento de ficheiros não está configurado.', 'armazenamento_indisponivel', 503)
        try:
            resposta['upload_url'] = _s3().generate_presigned_url(
                'put_object',
                Params={'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': chave_ficheiro, 'ContentType': mime},
                ExpiresIn=DURACAO_CHAVE,
            )
        except Exception:
            logger.exception('Falha ao gerar o URL pré-assinado')
            return _erro('Não foi possível preparar o envio. Tente novamente.', 'armazenamento_indisponivel', 503)
        resposta['chave_ficheiro'] = chave_ficheiro
    else:
        resposta['upload_url'] = f'/api/v1/teacher/envios/{chave}/'
    return Response(resposta, status=201)


def _marca_chave(chave):
    return 'envio-usado:' + hashlib.sha256(chave.encode('utf-8')).hexdigest()


def _ja_confirmado(conteudo, chave):
    """A chave já foi confirmada (marca na cache, ou o destino já aponta para este ficheiro)?"""
    if cache.get(_marca_chave(chave)):
        return True
    from apps.courses.models import Chapter, Course
    f, alvo, destino = conteudo['f'], conteudo['a'], conteudo['d']
    if destino == 'video':
        return Chapter.objects.filter(id=alvo, video__endswith=f).exists()
    if destino == 'material':
        return ChapterResource.objects.filter(chapter_id=alvo, external_url__endswith=f).exists()
    if destino == 'capa':
        return Course.objects.filter(id=alvo, image__endswith=f).exists()
    if destino == 'fotografia':
        from apps.users.models import User
        return User.objects.filter(id=alvo, avatar__endswith=f).exists()
    return False


def _resposta_ja_confirmado():
    return _erro('Este envio já foi confirmado. Para trocar o ficheiro, comece um envio novo.',
                 'envio_ja_confirmado', 409)


def _ler_chave(request, chave):
    """O conteúdo da chave, se for válida, recente e de quem pede; senão None."""
    if not isinstance(chave, str) or not chave:
        return None
    try:
        conteudo = signing.loads(chave, salt=SAL, max_age=DURACAO_CHAVE)
    except signing.BadSignature:  # inclui SignatureExpired
        return None
    if conteudo.get('u') != str(request.user.id):
        return None
    return conteudo


# ---------------------------------------------------------------------------
# 1. Pedir um envio
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes(PERMISSOES)
def iniciar_video(request, aula_id):
    aula = _aula_do_professor(request, aula_id)
    return _iniciar(request, 'video', aula.id, aula.section.course_id)


@api_view(['POST'])
@permission_classes(PERMISSOES)
def iniciar_material(request, aula_id):
    aula = _aula_do_professor(request, aula_id)
    return _iniciar(request, 'material', aula.id, aula.section.course_id)


@api_view(['POST'])
@permission_classes(PERMISSOES)
def iniciar_capa(request, curso_id):
    curso = _curso_do_professor(request, curso_id)
    if curso.course_type == 'practice':
        return _erro('Os cursos de prática não têm imagem de capa.', 'tipo_invalido')
    return _iniciar(request, 'capa', curso.id, curso.id)


@api_view(['POST'])
@permission_classes(PERMISSOES)
def iniciar_fotografia(request):
    """Fotografia do perfil do professor (fica em User.avatar)."""
    return _iniciar(request, 'fotografia', request.user.id, '')


# ---------------------------------------------------------------------------
# 2. Receber os bytes (só em modo local)
# ---------------------------------------------------------------------------

@api_view(['PUT', 'POST'])
@parser_classes([])
@permission_classes(PERMISSOES)
def envio_local(request, chave):
    if usa_s3():
        return _erro('Os ficheiros são enviados directamente para o armazenamento.', 'modo_invalido', 404)
    if not envios_locais_permitidos():
        return _resposta_sem_armazenamento()
    conteudo = _ler_chave(request, chave)
    if conteudo is None or conteudo.get('modo') != 'local':
        return _erro('Este envio expirou ou não é válido. Comece de novo.', 'envio_invalido', 404)
    if _ja_confirmado(conteudo, chave):
        return _resposta_ja_confirmado()
    limite = min(LIMITES[conteudo['d']], int(conteudo['t']) + 1024)
    try:
        caminho = _caminho_local(conteudo['f'])
    except ValueError:
        return _erro('Envio inválido.', 'envio_invalido', 404)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(caminho.name + '.parte')
    recebidos = 0
    origem = request._request
    try:
        with open(temporario, 'wb') as destino:
            while True:
                bloco = origem.read(1024 * 1024)
                if not bloco:
                    break
                recebidos += len(bloco)
                if recebidos > limite:
                    raise OverflowError
                destino.write(bloco)
    except OverflowError:
        temporario.unlink(missing_ok=True)
        return _erro('O ficheiro é maior do que o indicado.', 'ficheiro_invalido', 400)
    if recebidos == 0:
        temporario.unlink(missing_ok=True)
        return _erro('O ficheiro chegou vazio.', 'ficheiro_invalido', 400)
    os.replace(temporario, caminho)
    return Response({'recebido': True, 'tamanho_bytes': recebidos})


# ---------------------------------------------------------------------------
# 3. Confirmar
# ---------------------------------------------------------------------------

def _tamanho_guardado(conteudo):
    """Tamanho real do ficheiro já enviado, ou None se ainda não está lá."""
    if conteudo['modo'] == 'local':
        try:
            caminho = _caminho_local(conteudo['f'])
        except ValueError:
            return None
        return caminho.stat().st_size if caminho.is_file() else None
    try:
        cabeca = _s3().head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=conteudo['f'])
    except Exception:
        return None
    return int(cabeca.get('ContentLength') or 0) or None


@api_view(['POST'])
@permission_classes(PERMISSOES)
def confirmar(request):
    dados = _dados(request)
    conteudo = _ler_chave(request, dados.get('chave'))
    if conteudo is None:
        return _erro('Este envio expirou ou não é válido. Comece de novo.', 'envio_invalido',
                     details={'chave': ['Chave inválida ou expirada.']})
    if conteudo['modo'] != ('s3' if usa_s3() else 'local'):
        return _erro('Este envio já não é válido. Comece de novo.', 'envio_invalido')
    if conteudo['modo'] == 'local' and not envios_locais_permitidos():
        return _resposta_sem_armazenamento()
    if _ja_confirmado(conteudo, dados['chave']):
        return _resposta_ja_confirmado()

    destino = conteudo['d']
    if destino == 'fotografia':
        alvo = request.user
    elif destino == 'capa':
        alvo = _curso_do_professor(request, conteudo['a'])
    else:
        alvo = _aula_do_professor(request, conteudo['a'])

    tamanho = _tamanho_guardado(conteudo)
    if tamanho is None:
        return _erro('O ficheiro ainda não chegou. Envie-o antes de confirmar.', 'envio_em_falta')
    if tamanho > LIMITES[destino]:
        return _erro(f'O ficheiro é demasiado grande. O máximo é {LIMITES_TEXTO[destino]}.', 'ficheiro_invalido')

    url = url_publico(conteudo['f']) if conteudo['modo'] == 's3' else url_local(request, conteudo['f'])
    nome = conteudo['n']

    with transaction.atomic():
        if destino == 'video':
            alvo = type(alvo).objects.select_for_update().select_related('section__course').get(pk=alvo.pk)
            anterior = alvo.video
            alvo.video = url
            alvo.video_nome = nome
            alvo.video_tamanho = tamanho
            # Vídeo novo: a duração do anterior já não vale (volta a ser lida do ficheiro/registos).
            alvo.duracao_s = None
            campos = ['video', 'video_nome', 'video_tamanho', 'duracao_s']
            if alvo.type == 'Text':
                alvo.type = 'Video'
                campos.append('type')
            alvo.save(update_fields=campos + ['updated_at'])
            _tocar(alvo.section.course_id)
            resposta = aula_dict(alvo)
        elif destino == 'material':
            existente = ChapterResource.objects.filter(chapter=alvo, external_url=url).first()
            if existente is None:
                from django.db.models import Max
                ordem = (ChapterResource.objects.filter(chapter=alvo).aggregate(m=Max('order'))['m'] or 0) + 1
                existente = ChapterResource.objects.create(
                    chapter=alvo, title=nome[:200], resource_type=conteudo['r'], external_url=url,
                    file_size=tamanho, file_format=os.path.splitext(conteudo['f'])[1].lower()[:20],
                    order=ordem, created_by=request.user, access_level='enrolled',
                )
                _tocar(alvo.section.course_id)
            anterior = None
            resposta = material_dict(existente)
        elif destino == 'fotografia':
            from apps.users.professor import perfil_dict
            anterior = alvo.avatar
            alvo.avatar = url
            alvo.save(update_fields=['avatar', 'updated_at'])
            resposta = perfil_dict(alvo)
        else:
            anterior = alvo.image
            alvo.image = url
            alvo.save(update_fields=['image', 'updated_at'])
            resposta = detalhe_com_acesso(alvo)
        cache.set(_marca_chave(dados['chave']), 1, DURACAO_CHAVE + 60)
        if anterior and anterior != url:
            apagar_depois_do_commit([anterior])
    return Response(resposta)
