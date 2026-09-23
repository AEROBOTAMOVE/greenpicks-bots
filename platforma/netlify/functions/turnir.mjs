import { getApi } from "./_lib/runtime.mjs";

export default async (req, context) => getApi().turnir(req, context);

export const config = { path: "/api/turnir" };
