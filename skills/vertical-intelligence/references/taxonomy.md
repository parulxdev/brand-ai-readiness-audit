# 50-Vertical Taxonomy Reference

Keywords are matched against URL path (weight 5) and cleaned visible text
(weight 1) using word-boundary regex. A classification requires `score >= 4`
and a margin of `>= 2` over the runner-up (or `score >= 8` outright).

## Core Commercial (1-9)

1. **e-commerce** — cart, checkout, sku, add to cart, free shipping, buy now, shopping bag
2. **saas** — pricing, features, integrations, free trial, dashboard, software, subscription
3. **airline** — flight, airline, baggage, boarding pass, round trip, fare, skyteam
4. **hotel** — room rate, check-in, suites, amenities, book room, hotel, resort
5. **news** — breaking news, headline, editor, journalism, published on, opinion, editorial
6. **healthcare** — patients, doctors, clinic, specialties, medical center, physician
7. **real-estate** — properties, mortgage calculator, realtor, for sale, bedrooms, listing
8. **automotive** — dealership, test drive, vehicle, horsepower, car, sedan
9. **fintech** — payments, wallet, transfers, interest rate, crypto, banking, neobank

## Business & Professional Services (10-23)

10. **edtech** — curriculum, courses, syllabus, student portal, tuition, learning management
11. **medtech** — medical device, fda approval, diagnostics, clinical trial, biomedical
12. **legaltech** — contract lifecycle, e-discovery, compliance, litigation, legal practice
13. **proptech** — tenant portal, property management, lease tracking, smart building
14. **gaming** — gameplay, esports, multiplayer, steam, console, game developer
15. **aerospace** — avionics, satellite, propulsion, launch vehicle, aeronautical
16. **energy** — solar panels, renewable energy, grid, wind farm, power plant, utility
17. **cybersecurity** — threat intelligence, zero trust, firewall, endpoint security, siem
18. **cleantech** — carbon footprint, sustainability, decarbonization, circular economy
19. **insurtech** — claim status, underwriting, policyholder, deductible, insurance quote
20. **logistics** — freight, waybill, fleet management, last mile, warehousing, carrier
21. **hrtech** — applicant tracking, payroll, onboarding, talent acquisition, performance review
22. **martech** — campaign management, attribution, lead generation, marketing automation
23. **govtech** — public sector, citizen services, municipal, procurement, e-government

## Industrial & Frontier (24-31)

24. **agtech** — precision farming, crop yield, irrigation, agronomy, livestock tracking
25. **biotech** — genomics, therapeutics, molecular, recombinant, drug discovery
26. **deeptech** — quantum computing, nanotechnology, photonics, semiconductor
27. **ai-ml** — neural network, transformer model, large language model, inference, fine-tuning
28. **consulting** — advisory services, management consulting, case studies, deliverables
29. **venture-capital** — portfolio companies, seed round, series a, cap table, venture firm
30. **private-equity** — buyout, leveraged buyout, asset management, portfolio value
31. **wealth-management** — asset allocation, fiduciary, portfolio manager, estate planning

## Media & Entertainment (32-34)

32. **entertainment** — streaming, box office, episodes, cinema, discography, trailers
33. **sports** — league, tournament, scoreboard, coaching staff, athletics, playoffs
34. **publishing** — manuscript, monograph, academic press, periodical, imprint

## Lifestyle & Travel (35-42)

35. **travel** — itinerary, tour operator, sightseeing, excursion, destination guide
36. **hospitality** — concierge, hospitality services, banquet, guest experience
37. **restaurant** — menu, table reservation, takeout, dine-in, culinary, bistro
38. **fashion** — apparel, runway, haute couture, footwear, wardrobe, garment
39. **beauty** — skincare, cosmetics, dermatologist, makeup, fragrance
40. **fitness** — workout plan, gym membership, personal trainer, caloric deficit
41. **telecommunications** — broadband, 5g network, fiber optic, telecom operator, cellular
42. **banking** — checking account, mortgage rates, credit card, atm locator, wire transfer

## Industrial & Specialized (43-50)

43. **construction** — general contractor, blueprints, scaffolding, building permits
44. **manufacturing** — assembly line, oem, machining, supply chain, industrial equipment
45. **supply-chain** — inventory management, procurement, vendor management, logistics network
46. **defense** — defense contractor, military technology, tactical systems, national security
47. **non-profit** — donation, philanthropy, charitable, volunteer, 501c3, mission statement
48. **e-learning** — video course, self-paced, certification, instructor-led
49. **e-sports** — tournament bracket, prize pool, pro team, shoutcaster
50. **architecture** — architectural firm, elevation plans, structural design, cad drawings

## Fallback

**general** — returned when no vertical scores >= 4 or the top score is ambiguous.