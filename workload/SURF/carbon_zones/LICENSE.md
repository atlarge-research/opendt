# Carbon intensity traces: source and license

The files in this folder are a **derived subset** (October 2022, hourly) of the Electricity Maps
carbon-intensity datasets collected in the [opendc-traces](https://github.com/atlarge-research/opendc-traces)
repository (`carbon/traces/<ZONE>_2021-2024.parquet`). They were produced with
`tutorial/resources/make_carbon_subset.py`; values are unchanged, only rows outside October 2022 were dropped.

| File | Zone | Unit |
|---|---|---|
| `NL.parquet` | Netherlands | gCO2eq/kWh |
| `DE.parquet` | Germany | gCO2eq/kWh |
| `RO.parquet` | Romania | gCO2eq/kWh |
| `PL.parquet` | Poland | gCO2eq/kWh |
| `SE.parquet` | Sweden | gCO2eq/kWh |

## License

This database is made available under the **Open Database License (ODbL) v1.0**:
<https://opendatacommons.org/licenses/odbl/1-0/>. Any rights in individual contents of the database are
licensed under the same terms. If you redistribute or adapt this subset, keep this notice, credit
Electricity Maps, and share adapted versions under the ODbL.

## How to cite

> Electricity Maps (2025). Netherlands 2022 hourly Carbon Intensity Data (Version January 27, 2025). Electricity Maps. https://www.electricitymaps.com
>
> Electricity Maps (2025). Germany 2022 hourly Carbon Intensity Data (Version January 27, 2025). Electricity Maps. https://www.electricitymaps.com
>
> Electricity Maps (2025). Romania 2022 hourly Carbon Intensity Data (Version January 27, 2025). Electricity Maps. https://www.electricitymaps.com
>
> Electricity Maps (2025). Poland 2022 hourly Carbon Intensity Data (Version January 27, 2025). Electricity Maps. https://www.electricitymaps.com
>
> Electricity Maps (2025). Sweden 2022 hourly Carbon Intensity Data (Version January 27, 2025). Electricity Maps. https://www.electricitymaps.com
