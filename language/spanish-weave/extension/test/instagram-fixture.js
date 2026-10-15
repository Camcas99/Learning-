// Synthetic Instagram pages: modeled on instagram.com's structure (a feed post with its caption and comments, a
// profile header with the bio), not copied from it, with made-up people and text. Instagram changes its markup
// often, so check these shapes against the live site (DevTools on a feed post, a post's comments and a profile)
// before trusting the adapter in page.js.
export const FEED = `
<main role="main">
  <article id="post">
    <div>
      <a href="/sofia.travels/" role="link"><span dir="auto" id="author">sofia.travels</span></a>
      <span> • </span><time datetime="2026-10-14T18:00:00.000Z">1d</time>
      <!-- longer than Instagram's "Follow", so only the button guard can reject it -->
      <div role="button" tabindex="0"><span dir="auto" id="follow">Follow sofia.travels to see more posts like this</span></div>
    </div>
    <div><img alt="Photo by Sofia on October 14, 2026. May be an image of the beach and the ocean."></div>
    <section><span>1,204 likes</span></section>
    <div>
      <a href="/sofia.travels/" role="link"><span dir="auto">sofia.travels</span></a>
      <span dir="auto" id="caption">We finally reached the coast and the water was very warm,
        <span dir="auto" id="nested">so we stayed by the house until the light was gone</span>
        <a href="/explore/tags/travel/" role="link">#travel</a> with <a href="/marco.eats/" role="link">@marco.eats</a></span>
      <span>… <div role="button" tabindex="0"><span dir="auto" id="more">more</span></div></span>
    </div>
    <ul>
      <li><a href="/marco.eats/" role="link"><span dir="auto">marco.eats</span></a>
        <span dir="auto" id="comment-long">This looks amazing and I really want to go there next summer</span></li>
      <li><a href="/ana.photo/" role="link"><span dir="auto">ana.photo</span></a>
        <span dir="auto" id="comment-short">So pretty and calm!</span></li>
      <li><a href="/dr.lee/" role="link"><span dir="auto">dr.lee</span></a>
        <span dir="auto" id="comment-health">Bring sunscreen, and ask your doctor about medication for sunburn.</span></li>
    </ul>
  </article>
</main>`;

export const PROFILE = `
<main role="main">
  <header>
    <div><img alt="sofia.travels's profile picture"></div>
    <section>
      <div><h2>sofia.travels</h2><button type="button">Follow</button></div>
      <ul><li><span>248 posts</span></li><li><a href="/sofia.travels/followers/"><span>12.5K followers</span></a></li></ul>
      <div>
        <span>Sofia Reyes</span>
        <h1 dir="auto" id="bio">Writer and photographer. I travel with my dog and post a new story every week with <a href="/marco.eats/" role="link">@marco.eats</a></h1>
        <a href="https://example.com/sofia" rel="me nofollow noopener noreferrer" target="_blank"><span dir="auto">example.com/sofia</span></a>
      </div>
    </section>
  </header>
</main>`;
