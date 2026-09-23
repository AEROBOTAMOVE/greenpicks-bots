import { getApi } from "./_lib/runtime.mjs";

export default async (req, context) => getApi().pushKey(req, context);

export const config = { path: "/api/push-key" };
