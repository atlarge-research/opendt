# Grafana

Visualization dashboards for OpenDT metrics.

## Access

- **URL:** http://localhost:3000
- **Authentication:** Disabled (anonymous admin access)

The OpenDT dashboard is set as the home page.

## Dashboards

### Power Dashboard

Displays:
- **Power Consumption** - Actual vs simulated power draw over time
- **Carbon Emissions** - Estimated carbon emissions based on power and grid intensity

Data is queried from the OpenDT API at `http://dashboard:8000`.

## Provisioning

Dashboards in `provisioning/dashboards/` are auto-provisioned on startup. These are read-only templates.

To create an editable copy:
1. Open the dashboard
2. Click title → **Save As**
3. Save with a new name

Custom dashboards are persisted in the Docker volume.

## Data Sources

The [Infinity datasource](https://grafana.com/grafana/plugins/yesoreyeram-infinity-datasource/) is pre-configured to query JSON endpoints from the OpenDT API.

## Persistence

Dashboard data is stored in the `opendt-grafana-storage` Docker volume. To reset:

```
make clean-volumes
```

## Related

- [dashboard](../dashboard/README.md) - API that provides data
