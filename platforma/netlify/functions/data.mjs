import { getApi } from "./_lib/runtime.mjs";

export default async (req, context) => getApi().data(req, context);

export const config = { path: "/api/data" };
