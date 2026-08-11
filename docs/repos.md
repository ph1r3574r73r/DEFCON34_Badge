# Links & repos

Official how-to and link graph: [defcon.org/34b](https://defcon.org/34b). Host tools: [development.md](development.md). Credits: [CREDITS.md](CREDITS.md).

**Caution:** flashing custom / developer-signed firmware enters developer mode and erases conference secrets. Unsigned BIO / OLED uploads over the stock console path are different — see [development.md](development.md).

---

## Official sources

| Source | URL |
| --- | --- |
| Badge help | https://defcon.org/34b |
| News (Badge Alert + Meet the badge) | https://defcon.org/html/defcon-34/dc-34-news.html |
| Wired — Zetter exclusive | https://www.wired.com/story/defcon-34-badge-baochip-andrew-bunnie-huang/ |
| DEF CON 34 — bunnie talk (Video Team) | https://www.youtube.com/watch?v=1plmJlWSKa0 |
| Media (KiCad, photos, UF2) | https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/ |
| SAO spec PDF | https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20SAO%20Spec%20Sheet.pdf |
| Firmware (DEF CON) | https://defcon.org/34b/latest.zip |
| Firmware (Baochip CI) | https://ci.betrusted.io/releases/latest/baochip/dc34-badge/latest.zip |
| CHEESO story & design | https://cheeso.io/defcon-34-badge |
| Baochip | https://baochip.com/ |
| Baochip-1x coder’s guide | https://baochip.github.io/baochip-1x/ |
| bunnie — Baochip-1x post | https://www.bunniestudios.com/blog/2026/baochip-1x-a-mostly-open-22nm-soc-for-high-assurance-applications/ |
| IRIS | https://bunnie.org/iris · [paper](https://arxiv.org/abs/2303.07406) |
| Xous Book | https://betrusted.io/xous-book/ |
| Discord (Baochip) | https://discord.gg/hyWrYz7fa |
| Discord (DEF CON) | https://discord.gg/defcon |
| Matrix | https://matrix.to/#/#precursor.dev:matrix.org |

Browser extensions (token mode): [Chrome](https://chrome.google.com/webstore/detail/fbjafgnnhopnfkbiegkgncbhadjcgoap) · [Firefox](https://addons.mozilla.org/addon/baochip-qr/)

---

## Official badge (bunnie)

| Repo | What it is |
| --- | --- |
| [bunnie/dc34-vault](https://github.com/bunnie/dc34-vault) | Token + conference UI. **Build instructions.** [`defcon-scheme.md`](https://github.com/bunnie/dc34-vault/blob/main/defcon-scheme.md) = light / `k0` game. |
| [bunnie/dc34-console](https://github.com/bunnie/dc34-console) | REPL, power, LED / BIO lightgenes. |
| [bunnie/dc34-api](https://github.com/bunnie/dc34-api) | Shared crate: `BadgeType`, Haploid/Diploid, IPC. |
| [bunnie/dc34-core-hw](https://github.com/bunnie/dc34-core-hw) | Core module KiCad (CERN OHL-W-2.0). Carriers on [media.defcon.org](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/). |
| [bunnie/dc34-image](https://github.com/bunnie/dc34-image) | Host: 128×128 OLED upload over USB-serial. |
| [bunnie/dc34-bio](https://github.com/bunnie/dc34-bio) | Host: BIO binary upload (SAO / PicoRV). |
| [bunnie/dabao-tester-app](https://github.com/bunnie/dabao-tester-app) | Example stand-alone Xous app (Dabao). |

---

## Silicon / BIO / eval (baochip)

| Repo | What it is |
| --- | --- |
| [baochip/baochip-1x](https://github.com/baochip/baochip-1x) | Mostly-open RTL + [SoC diagram](https://github.com/baochip/baochip-1x/blob/main/docs/src/images/soc-top-diagram.png). |
| [baochip/bio-sim](https://github.com/baochip/bio-sim) | BIO CPU RTL sim. |
| [baochip/bio-loader](https://github.com/baochip/bio-loader) | Load BIO onto Dabao via serial. |
| [baochip/dabao](https://github.com/baochip/dabao) | Dabao eval-board KiCad. |

CI: [bao1x](https://ci.betrusted.io/bao1x/) · [bao1x-cpu](https://ci.betrusted.io/bao1x-cpu/) · [BIO-surfer](https://baochip.com/bio-surfer/).

---

## OS / SDKs / boot verify

| Repo | What it is |
| --- | --- |
| [betrusted-io/xous-core](https://github.com/betrusted-io/xous-core) | Xous microkernel. [README-baochip](https://github.com/betrusted-io/xous-core/blob/main/README-baochip.md). |
| [sbellem/baobit](https://github.com/sbellem/baobit) | Guix-reproducible boot0/boot1 vs device audit. |
| [ArmstrongSubero/dabao-sdk](https://github.com/ArmstrongSubero/dabao-sdk) | Third-party C SDK (linked from 34b). |
| [MicroPython port (discussion)](https://github.com/orgs/micropython/discussions/19580) | WIP; Dabao target. |

---

## Community

Useful writeups and tools. Treat as research / toys — not ship firmware.

| Repo / writeup | Notes |
| --- | --- |
| [amattas — Only 132 Bytes…](https://www.anthonymattas.com/articles/only-132-bytes) | Sealed loader hop. This tree’s [`tools/132hop`](../tools/132hop/) rebuilds that class (QR-on-OLED variant). |
| [vmfunc/dc34-badge](https://github.com/vmfunc/dc34-badge) | Soft-path dead ends; silicon ACL notes. |
| [jonfen/dc34-badge](https://github.com/jonfen/dc34-badge) | Gene-crypto / `k0` tooling. |
| [thehinac/dc34_badge](https://github.com/thehinac/dc34_badge) | QR / serial footguns; `test k0` overwrite warning. |
| [szatmary/baochip-1x-security-review](https://github.com/szatmary/baochip-1x-security-review) | Unverified RTL finding list (AI-assisted). |
| [noodlemctwoodle/dc34-badge](https://github.com/noodlemctwoodle/dc34-badge) | Front LED BIO demos. |
| [mmcjcc/dc34-badge-tools](https://github.com/mmcjcc/dc34-badge-tools) | USB-serial / OLED helpers. |
| [ace42588/baochip-doom](https://github.com/ace42588/baochip-doom) | DOOM on Baochip. |
| [itseyesack/dc34b-imbadginator](https://github.com/itseyesack/dc34b-imbadginator) | Android OLED uploader. |
| [lnxgod/dc34-badge-manager-android](https://github.com/lnxgod/dc34-badge-manager-android) | Android badge manager. |
| [zitterbewegung/dc34-baogram](https://github.com/zitterbewegung/dc34-baogram) | Photo-sharing app. |

### Browser toys

| Site | Notes |
| --- | --- |
| [defcon.nsakek.com](https://defcon.nsakek.com/) | `ohyou_` light lab |
| [badge.sex](https://badge.sex) | Breed social |
| [gamechangersai.org/dc34badge](https://gamechangersai.org/dc34badge) | OLED / lights UI |
| [dc34.ithst.de](https://dc34.ithst.de/) | Light UI (third-party key paste) |
| [The Light Bank](https://ph1r3574r73r.github.io/DEFCON34_Badge/) | This repo’s donor gene designer ([source](../tools/genomics/)) |

### Press & commentary

| Source | URL |
| --- | --- |
| Reddit — Wired x-post | https://www.reddit.com/r/Defcon/comments/1vbt117/the_new_defcon_badges_pack_a_unique_open_source/ |
| Techmeme | https://www.techmeme.com/260801/p10 |
| Tweakers / TNV (NL) | https://technieuwsvandaag.nl/nederlands-ontwerp-def-con-badge/ |
| Emerick — root of trust | https://www.linkedin.com/pulse/def-con-34-baochip-badge-analysis-shift-hardware-root-joseph-emerick-5zcic |
| Hackster | https://www.hackster.io/news/the-def-con-34-badge-packs-a-surprise-andrew-bunnie-huang-s-mostly-open-baochip-x1-1e03307d4797 |
| TechTimes | https://www.techtimes.com/articles/322671/20260802/def-con-34-badge-features-first-verifiable-open-source-silicon-production-scale.htm |
| Darknet Diaries 87 (Yafsec) | https://darknetdiaries.com/episode/87/ |

---

## Adjacent

| Project | Notes |
| --- | --- |
| [Wietsman/wiccon_badge_2023](https://github.com/Wietsman/wiccon_badge_2023) | Prior Dutch badge by the DC34 carrier router. |
| Precursor / Betrusted | Earlier high-assurance work by bunnie. |
| Dabao | Baochip-1x eval board ([Crowd Supply](https://www.crowdsupply.com/)). |
| Pavona | Open-source silicon consortium. |
| Crossbar | Tape-out host ([crossbar-inc.com](https://crossbar-inc.com/)). |
