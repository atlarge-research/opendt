# Grafana with its plugins at fixed versions, installed in the image: `make up` wipes the Grafana volume, and the
# demo then needs no internet
FROM grafana/grafana:12.4.13

# no download of Grafana's default apps at start either
ENV GF_PATHS_PLUGINS=/opt/plugins GF_PLUGINS_PREINSTALL_DISABLED=true
USER root
RUN grafana cli --pluginsDir "$GF_PATHS_PLUGINS" plugins install yesoreyeram-infinity-datasource 3.11.1 \
    && grafana cli --pluginsDir "$GF_PATHS_PLUGINS" plugins install volkovlabs-form-panel 6.3.5
USER grafana
