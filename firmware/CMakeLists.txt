cmake_minimum_required(VERSION 3.16)

# CI passes the version (git describe) and the GitHub Pages address of the repo it built from,
# so a fork's robots pull updates from the fork's own Pages site.
if(DEFINED ENV{FW_VERSION})
    set(PROJECT_VER "$ENV{FW_VERSION}")
else()
    set(PROJECT_VER "dev")
endif()

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(cardboard-bot)
