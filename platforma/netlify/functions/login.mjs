import { getApi } from "./_lib/runtime.mjs";

export default async (req, context) => getApi().login(req, context);

export const config = { path: "/api/login" };
