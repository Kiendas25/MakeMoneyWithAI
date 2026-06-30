/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ENGINE_WS_PORT?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
