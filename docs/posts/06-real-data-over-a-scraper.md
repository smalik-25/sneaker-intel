# Choosing real data over a flaky scraper

The original plan had three live sources: eBay sold listings, Reddit, and Google
Trends. Partway through I hit the question every data project hits eventually —
where does the *real* data actually come from? — and the answer changed the shape
of the project.

The honest constraints: eBay and Reddit both need API keys and approval, and the
tempting shortcut, a community scraper that pulls StockX/GOAT/Flight Club prices,
turned out to be exactly the kind of thing you don't want load-bearing. It scrapes
sites behind anti-bot protection, has open issues about 403 errors when those
protections tighten, and it's Node where the rest of my project is Python. Great
for a hobby tracker; a bad foundation for something with my name on it that I
want to demo reliably.

So I split the difference. The real-data backbone is the **Kaggle StockX 2019
dataset** — about 99K real Off-White and Yeezy resale sales, with sale price,
retail price, release date, size, and region. No keys, no scraping, no terms-of-
service gray area, and it won't break the morning before an interview. It maps
almost one-to-one onto the schema I'd already built: sales into `fact_sales`, and
the loader derives `dim_drops` (retail price and release date) straight from the
data instead of me hand-seeding it. I kept Google Trends too, because it's a
genuinely live, key-free demand signal.

The part I thought hardest about was what *not* to throw away. I'd already written
the eBay and Reddit clients — real API integration, the kind of thing that's
worth showing. Deleting them would trade away a genuine skill demonstration for a
slightly tidier repo. So I reframed them as documented, tested, schema-ready
*future extensions*. The loader and warehouse already support them; enabling them
later is purely additive. The interview story becomes "multi-source ingestion
with live API clients plus a real historical dataset," which reads as more mature
than either alone.

One detail that mattered for correctness: StockX names are slugs like
`Adidas-Yeezy-Boost-350-V2-Zebra`. I normalize those into clean text and use that
as the single conformed key in `dim_shoes`, so the sales data and the live Trends
signal land on the *same* shoe row instead of two near-duplicates that never join.
Tiny normalization step, but it's the difference between a star schema that works
and one that quietly doesn't.

The lesson I'm taking from this: "real data" doesn't have to mean "live API." A
solid public dataset, wired in cleanly, beats a fragile live feed for a project
whose point is the engineering around the data.
