import { getApi } from "./_lib/runtime.mjs";

export default async (req, context) => getApi().me(req, context);

export const config = { path: "/api/me" };
