# Sources the daily discovery agent pulls from.
# The agent fetches all three groups each run.

## Reddit — Atom RSS (no auth)
# Primary source: explicit "build this" requests + new project chatter.
https://www.reddit.com/r/SomebodyMakeThis/new/.rss
https://www.reddit.com/r/AppIdeas/new/.rss
https://www.reddit.com/r/SideProject/new/.rss
https://www.reddit.com/r/lightbulb/new/.rss
https://www.reddit.com/r/selfhosted/new/.rss
https://www.reddit.com/r/RequestABot/new/.rss

## Hacker News — Algolia JSON API (no auth)
# "Ask HN" = explicit asks. "Show HN" = inspiration on what people just built.
https://hn.algolia.com/api/v1/search_by_date?tags=ask_hn&hitsPerPage=30
https://hn.algolia.com/api/v1/search_by_date?tags=show_hn&hitsPerPage=30

## GitHub Trending — HTML (no auth, scrape)
# Supplementary signal — what topics are hot this week.
# Use to *flavor* an idea, not as direct ask source.
https://github.com/trending?since=daily
