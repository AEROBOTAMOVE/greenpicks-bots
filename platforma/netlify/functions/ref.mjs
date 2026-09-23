import { getApi } from "./_lib/runtime.mjs";

export default async (req, context) => getApi().ref(req, context);

export const config = { path: "/api/ref" };
