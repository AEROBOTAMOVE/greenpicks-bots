/* The Green Room · свързването с Netlify (база + променливи на средата)
   Единственият модул, който внася @netlify/database. Всичко се създава
   мързеливо при първата заявка — нищо не се изпълнява при зареждане. */
import { getDatabase } from "@netlify/database";
import { makeRepo } from "./repo.mjs";
import { makeApi } from "./api.mjs";
import { makeDataSource } from "./data.mjs";
import { adminSet } from "./core.mjs";
import { ADMIN_HASHES } from "./admins.mjs";

let api = null;

function readEnv(name) {
  try {
    return (globalThis.Netlify && globalThis.Netlify.env && globalThis.Netlify.env.get(name)) || "";
  } catch (e) {
    return "";
  }
}

export function getApi() {
  if (!api) {
    const db = getDatabase();
    const sql = (strings, ...values) => db.sql(strings, ...values);
    api = makeApi({
      repo: makeRepo(sql),
      // администраторите: sha256 хешове от admins.mjs + ADMIN_EMAILS от Netlify
      adminEmails: () => adminSet(ADMIN_HASHES, readEnv("ADMIN_EMAILS")),
      data: makeDataSource(),
    });
  }
  return api;
}
