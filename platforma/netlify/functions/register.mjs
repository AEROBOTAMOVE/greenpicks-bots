import { getApi } from "./_lib/runtime.mjs";

export default async (req, context) => getApi().register(req, context);

export const config = { path: "/api/register" };
