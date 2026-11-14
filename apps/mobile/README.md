# ProEnglish — app móvel do estudante

App Expo (SDK 58, expo-router, TypeScript) com a área do estudante: conta, início, cursos em vídeo, laboratório de prática, conversa com o tutor, perfil e subscrição (Multicaixa Express simulado). Os ecrãs seguem as telas do telemóvel do canvas "ProEnglish: telas" e o comportamento da web (`apps/web`).

## Correr

```bash
npm install
npx expo run:ios        # versão de desenvolvimento no simulador (precisa de Xcode)
npx expo run:android    # idem no Android
npx expo start          # depois de instalada, só o servidor de desenvolvimento
```

A conversa por voz (Daily/WebRTC) e o Google exigem uma versão de desenvolvimento: não funcionam no Expo Go. Na web (`npx expo start --web`) a app abre para desenvolvimento, sem voz nem notificações.

## Configuração

| Variável | Para quê |
| --- | --- |
| `EXPO_PUBLIC_API_URL` | API Django (`…/api/v1`). Por omissão `http://localhost:8000/api/v1`; num telemóvel físico use o IP do computador. |
| `EXPO_PUBLIC_SITE_URL` | Site público (termos, privacidade, verificação de certificados). |
| `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID`, `EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID`, `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` | Entrar com o Google. Os mesmos ids vão para `GOOGLE_OAUTH2_CLIENT_IDS_APP` na API. |

Para a web de desenvolvimento, a API precisa de `http://localhost:8081` em `CORS_ALLOWED_ORIGINS`.

## Sessão

Os pedidos levam `X-Cliente: app`: a API devolve os tokens no corpo (`tokens: {access, refresh}`) em vez de cookies. O refresh fica no cofre do telemóvel (expo-secure-store); o access só em memória e é renovado sozinho num 401.

## Organização

- `src/app` — rotas: `(conta)` sem sessão; `(app)/(tabs)` os 5 separadores; o resto abre por cima.
- `src/ui` e `src/tema.ts` — sistema de design ProEnglish (não inventar cores).
- `src/api` — RTK Query (uma só `api`; cada domínio usa `injectEndpoints`), tokens e erros.
- `src/dominios/<área>` — endpoints e regras de cada área; `src/componentes/<área>` — peças de cada área.

Antes de entregar: `npx tsc --noEmit` e `npx expo lint`.
