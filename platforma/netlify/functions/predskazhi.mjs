import { getApi } from "./_lib/runtime.mjs";

export default async (req, context) => getApi().predskazhi(req, context);

export const config = { path: "/api/predskazhi" };
