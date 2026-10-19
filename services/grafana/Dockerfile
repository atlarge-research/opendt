# Grafana with its plugins at fixed versions, installed in the image: `make up` wipes the Grafana volume, and the
# demo then needs no internet
FROM grafana/grafana:12.4.13

# no download of Grafana's default apps at start either
ENV GF_PATHS_PLUGINS=/opt/plugins GF_PLUGINS_PREINSTALL_DISABLED=true
# the new dashboard layout (public preview in 12.4): panels shown or hidden by the plots people pick
ENV GF_FEATURE_TOGGLES_ENABLE=dashboardNewLayouts,kubernetesDashboards
USER root
RUN grafana cli --pluginsDir "$GF_PATHS_PLUGINS" plugins install yesoreyeram-infinity-datasource 3.11.1 \
    && grafana cli --pluginsDir "$GF_PATHS_PLUGINS" plugins install volkovlabs-form-panel 6.3.5 \
    && grafana cli --pluginsDir "$GF_PATHS_PLUGINS" plugins install volkovlabs-table-panel 3.6.8 \
    && grafana cli --pluginsDir "$GF_PATHS_PLUGINS" plugins install marcusolsson-dynamictext-panel 6.3.0
USER grafana
