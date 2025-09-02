import { error } from "@sveltejs/kit";
import { fetch_media_item } from "$lib/api";

/** @type {import('./$types').PageLoad} */
export async function load({ params }) {
  const id = params.slug;
  const data = await fetch_media_item(id);

  if (data && !data.error) {
    return data;
  } else {
    return {
      error: "couldn't find media item",
      status: data?.status || 404,
    };
  }
}
