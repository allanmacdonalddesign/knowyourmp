// Cloudflare Pages Function: POST /api/postal
//
// Turns a postal code into the address of that riding's MP page. The code is read from the request body, sent to the
// public Represent API to find the riding, and then dropped: it is never logged or stored, and never put in the
// address we redirect to. (Browsers cannot call Represent directly, so this tiny relay is needed on a static site.)

const CONTACT = "allanmacdonald.design@gmail.com";

export async function onRequestPost({ request, env }) {
  const to = (path) => Response.redirect(new URL(path, request.url).toString(), 303);

  let code = "";
  try {
    code = String((await request.formData()).get("code") || "");
  } catch {
    return to("/?error=postal");
  }
  code = code.replace(/\s+/g, "").toUpperCase();
  if (!/^[A-Z]\d[A-Z]\d[A-Z]\d$/.test(code)) return to("/?error=postal");

  let data;
  try {
    const r = await fetch(`https://represent.opennorth.ca/postcodes/${code}/`, {
      headers: { "User-Agent": `knowyourmp (${CONTACT})` },
    });
    if (r.status === 404) return to("/?error=notfound");
    if (!r.ok) return to("/?error=down");
    data = await r.json();
  } catch {
    return to("/?error=down");
  }

  // Match on name + riding against the list the site was built from.
  let index;
  try {
    index = await (await env.ASSETS.fetch(new URL("/search.json", request.url))).json();
  } catch {
    return to("/?error=down");
  }
  const reps = [...(data.representatives_centroid || []), ...(data.representatives_concordance || [])].filter(
    (x) => x.elected_office === "MP",
  );
  const slugs = [
    ...new Set(
      reps.map((rep) => index.find((m) => m.name === rep.name && m.riding === rep.district_name)?.slug).filter(Boolean),
    ),
  ];

  if (slugs.length === 1) return to(`/mp/${slugs[0]}/`);
  if (slugs.length > 1) return to(`/?choose=${slugs.join(",")}`); // split postal code: let the visitor pick
  return to("/?error=notfound");
}

// Anything else (someone opening /api/postal directly) goes back to the search page.
export async function onRequestGet({ request }) {
  return Response.redirect(new URL("/", request.url).toString(), 303);
}
