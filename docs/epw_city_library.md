# EPW City Library

The PUE Solver UI supports local EPW auto matching without using online downloads or a backend API.

## Directory Layout

Put local EPW files here:

```text
pue-solver-main/data/epw/
```

The frontend reads:

```text
pue-solver-main/data/epw_index.json
```

The inventory document is generated at:

```text
pue-solver-main/data/epw_inventory.md
```

## Add a New City EPW

1. Copy the `.epw` file into `pue-solver-main/data/epw/`.
2. From the repository root, run:

   ```bash
   python tools/build_epw_index.py
   ```

3. Review `pue-solver-main/data/epw_index.json`.
4. Add manual aliases if useful. For example:

   ```json
   "aliases": ["Shanghai", "上海", "Shanghai Hongqiao"]
   ```

5. Run the script again whenever new EPW files are added. Existing manual aliases are preserved.

## Add Shanghai / Tokyo / Singapore

Place the actual EPW file under `pue-solver-main/data/epw/`, then run:

```bash
python tools/build_epw_index.py
```

After generation, manually add local-language aliases if needed:

- Shanghai: add `上海`
- Tokyo: add `東京`, `东京`
- Singapore: add `Singapore`, `新加坡`

Do not add a city to `epw_index.json` unless the matching `.epw` file exists under `pue-solver-main/data/epw/`.

## Recommended Starter City List

Priorities:

- High: common data center project cities
- Medium: occasional project cities
- Low: reserve / backup locations

### China

| City | Country | Priority |
|---|---|---|
| Shanghai | China | High |
| Beijing | China | High |
| Shenzhen | China | High |
| Guangzhou | China | High |
| Chengdu | China | Medium |
| Hong Kong | China | High |

### Japan

| City | Country | Priority |
|---|---|---|
| Tokyo | Japan | High |
| Osaka | Japan | Medium |

### Singapore

| City | Country | Priority |
|---|---|---|
| Singapore | Singapore | High |

### Europe

| City | Country | Priority |
|---|---|---|
| Frankfurt | Germany | High |
| London | United Kingdom | High |
| Paris | France | Medium |
| Amsterdam | Netherlands | High |
| Dublin | Ireland | High |

### Middle East

| City | Country | Priority |
|---|---|---|
| Dubai | United Arab Emirates | Medium |

### India

| City | Country | Priority |
|---|---|---|
| Mumbai | India | High |
| Chennai | India | Medium |
| Bangalore | India | Medium |

### Australia

| City | Country | Priority |
|---|---|---|
| Sydney | Australia | Medium |
| Melbourne | Australia | Medium |

## How To Add A New City

1. Download a real EPW file for the target city or nearest suitable weather station.
2. Place the `.epw` file under:

   ```text
   pue-solver-main/data/epw/
   ```

3. From the repository root, run:

   ```bash
   python tools/build_epw_index.py
   ```

4. If needed, supplement aliases in `pue-solver-main/data/epw_index.json`, for example:

   ```text
   Shanghai -> 上海
   Tokyo -> 东京 / 東京
   Singapore -> 新加坡
   ```

5. Test in the UI:

   - Enter the city name in `Location`.
   - Click `Auto Match EPW`.
   - Confirm the UI shows `Climate matched`.

Do not edit solver logic when adding cities. The city library only affects local EPW selection.

## Test Auto Match EPW

1. Start the UI with `start_ui_server.bat`.
2. Open:

   ```text
   http://127.0.0.1:8000/index.html
   ```

3. Enter a location in the project location field.
4. Click `Auto Match EPW`.
5. Confirm the weather status shows a local EPW match.
6. If no city matches, the UI should show:

   ```text
   No local EPW matched. Please upload EPW manually.
   ```

Manual EPW upload remains available and takes priority until the user clicks `Auto Match EPW` again.
