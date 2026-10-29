idf_component_register(
    SRCS "main.c" "config.c" "config_json.c" "control.c" "hw.c" "store.c" "net.c" "web.c" "dns.c" "ota.c"
    INCLUDE_DIRS "."
    REQUIRES esp_driver_gpio esp_driver_ledc esp_driver_rmt esp_adc esp_wifi esp_netif esp_event nvs_flash
             esp_http_server esp_https_server esp_http_client esp_https_ota app_update esp_partition
             esp_timer json mbedtls lwip
    EMBED_TXTFILES "certs/servercert.pem" "certs/prvtkey.pem")

target_compile_options(${COMPONENT_LIB} PRIVATE -Wno-format-truncation -Wno-stringop-truncation)

if(DEFINED ENV{FW_PAGES_BASE})
    target_compile_definitions(${COMPONENT_LIB} PRIVATE FW_PAGES_BASE="$ENV{FW_PAGES_BASE}")
endif()

# The phone page is gzipped at build time and served as-is
idf_build_get_property(python PYTHON)
set(GZ ${CMAKE_CURRENT_BINARY_DIR}/index.html.gz)
add_custom_command(OUTPUT ${GZ}
    COMMAND ${python} ${CMAKE_CURRENT_SOURCE_DIR}/www/gz.py ${CMAKE_CURRENT_SOURCE_DIR}/www/index.html ${GZ}
    DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/www/index.html ${CMAKE_CURRENT_SOURCE_DIR}/www/gz.py
    VERBATIM)
add_custom_target(www_gz DEPENDS ${GZ})
add_dependencies(${COMPONENT_LIB} www_gz)
target_add_binary_data(${COMPONENT_LIB} ${GZ} BINARY)
