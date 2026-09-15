import { getApi } from "./_lib/runtime.mjs";

export default async (req, context) => getApi().adminUser(req, context);

export const config = { path: "/api/admin/user" };
