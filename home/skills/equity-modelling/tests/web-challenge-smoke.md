# Web-challenge smoke test

Run during the real-company pilot. These cases test research behaviour, not model inputs. Use the
underlying primary source, not a search-result snippet, and do not write any result into the pilot
workbook.

Primary fixture: Apple's 2024 Form 10-K filed with the SEC:
<https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm>

| Case | Challenge | Expected result |
|---|---|---|
| Known true | “Apple's fiscal 2024 total net sales were $391.035 billion.” | Find the 2024 total net sales figure in the filing, quote it with URL/date/basis, and mark the claim supported. |
| Known false | “Apple's fiscal 2024 total net sales were $491.035 billion.” | Find the filing's $391.035 billion figure, record the contradiction, and alert the user. |
| Ambiguous | “Apple Vision Pro was commercially successful in fiscal 2024.” | Explain that “commercially successful” is undefined and the filing does not provide a product-specific success threshold; keep the claim unresolved rather than forcing true/false. |

Pass only when all three records include the challenged claim, exact primary-source passage where
one exists, URL, publication/filing date, basis, and materiality; the ambiguous case stays
ambiguous; and no web-only number enters `sources.csv`, `forecast_inputs.csv`, or the workbook.
