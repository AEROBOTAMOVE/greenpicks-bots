import { getApi } from "./_lib/runtime.mjs";

export default async (req, context) => getApi().preview(req, context);

export const config = { path: "/api/preview" };
