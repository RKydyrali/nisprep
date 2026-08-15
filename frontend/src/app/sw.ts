import { defaultCache } from "@serwist/next/worker";
import type { PrecacheEntry, SerwistGlobalConfig } from "serwist";
import { NetworkFirst, Serwist, StaleWhileRevalidate } from "serwist";

declare global {
  interface WorkerGlobalScope extends SerwistGlobalConfig {
    __SW_MANIFEST: (PrecacheEntry | string)[] | undefined;
  }
}

declare const self: ServiceWorkerGlobalScope;

const OFFLINE_PAGE = "/ru/offline";

const serwist = new Serwist({
  precacheEntries: self.__SW_MANIFEST,
  skipWaiting: true,
  clientsClaim: true,
  navigationPreload: true,
  runtimeCaching: [
    // Страницы (/, /ru/*, /kk/*): NetworkFirst с фолбэком на кеш
    {
      matcher: ({ request }) => request.mode === "navigate",
      handler: new NetworkFirst({
        networkTimeoutSeconds: 4,
        cacheName: "danyshpan-pages",
      }),
      method: "GET",
    },
    // Статика (JS/CSS/шрифты/картинки/manifest): StaleWhileRevalidate
    {
      matcher: ({ request }) =>
        request.destination === "script" ||
        request.destination === "style" ||
        request.destination === "font" ||
        request.destination === "image" ||
        request.destination === "manifest",
      handler: new StaleWhileRevalidate({
        cacheName: "danyshpan-static",
      }),
      method: "GET",
    },
    ...defaultCache,
  ],
  fallbacks: {
    entries: [
      {
        url: OFFLINE_PAGE,
        matcher({ request }) {
          return request.destination === "document";
        },
      },
    ],
  },
});

serwist.addEventListeners();
