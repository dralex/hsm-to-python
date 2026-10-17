cmake_minimum_required(VERSION 3.16)

# the Debian package of the generator, its commands and its editor plugin;
# nothing is compiled
project(hsm-to-python VERSION 2.0.0 LANGUAGES NONE)

# the place of the pure Python modules on Debian
set(PYTHON_INSTALL_DIR "lib/python3/dist-packages" CACHE STRING
    "the directory of the modules under the prefix")
# the system plugin folder of CyberiadaPro
set(PLUGIN_INSTALL_DIR "share/cyberiada-pro/plugins/hsm-to-python")
set(DOC_INSTALL_DIR "share/doc/python3-hsm-to-python")
# the package directories do not follow the umask of the build
set(CMAKE_INSTALL_DEFAULT_DIRECTORY_PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE
    GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE)

install(FILES ${CMAKE_CURRENT_SOURCE_DIR}/gencode.py
              ${CMAKE_CURRENT_SOURCE_DIR}/hsm.py
              ${CMAKE_CURRENT_SOURCE_DIR}/hsmcheck.py
              ${CMAKE_CURRENT_SOURCE_DIR}/hsmplugin.py
        DESTINATION ${PYTHON_INSTALL_DIR})

# the commands, as the wheel's entry points make them
foreach(command_module "hsm-run;hsm" "hsm-gencode;gencode" "hsm-check;hsmcheck")
  list(GET command_module 0 command)
  list(GET command_module 1 module)
  file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/${command}
       "#!/usr/bin/python3\nimport sys\nfrom ${module} import run\nsys.exit(run())\n")
  install(PROGRAMS ${CMAKE_CURRENT_BINARY_DIR}/${command} DESTINATION bin)
endforeach()

install(FILES ${CMAKE_CURRENT_SOURCE_DIR}/editor-plugin/plugin.json
        DESTINATION ${PLUGIN_INSTALL_DIR})
install(FILES ${CMAKE_CURRENT_SOURCE_DIR}/editor-plugin/i18n/ru.json
        DESTINATION ${PLUGIN_INSTALL_DIR}/i18n)
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/editor-plugin/icons
        DESTINATION ${PLUGIN_INSTALL_DIR})

install(FILES ${CMAKE_CURRENT_SOURCE_DIR}/ChangeLog.md
              ${CMAKE_CURRENT_SOURCE_DIR}/README.md
              ${CMAKE_CURRENT_SOURCE_DIR}/LICENSE
        DESTINATION ${DOC_INSTALL_DIR})

# the machine-readable (DEP-5) copyright, where the Debian policy wants it
install(FILES ${CMAKE_CURRENT_SOURCE_DIR}/debian-copyright
        DESTINATION ${DOC_INSTALL_DIR} RENAME copyright)
install(FILES ${CMAKE_CURRENT_SOURCE_DIR}/docs/COMMENTS.md
        DESTINATION ${DOC_INSTALL_DIR}/docs)

# the tests need the hsmd and CyberiadaML modules in this Python
# (-DPython3_EXECUTABLE=... selects another one)
find_package(Python3 3.8 COMPONENTS Interpreter)
if(Python3_FOUND)
  enable_testing()
  add_test(NAME diagrams
           COMMAND ${Python3_EXECUTABLE} -B python_hsm_test.py
           WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/test)
  add_test(NAME arguments
           COMMAND ${Python3_EXECUTABLE} -B arguments_test.py
           WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/test)
  add_test(NAME standalone
           COMMAND ${Python3_EXECUTABLE} -B standalone_test.py
           WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/test)
  add_test(NAME model
           COMMAND ${Python3_EXECUTABLE} -B model_test.py
           WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/test)
  add_test(NAME plugin
           COMMAND ${Python3_EXECUTABLE} -B plugin_test.py
           WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/test)
  add_test(NAME runner
           COMMAND ${Python3_EXECUTABLE} -B runner_test.py
           WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/test)
endif()

# optional per-release suffix (e.g. ubuntu2404) for the package version: the
# package is tested against that release's libraries and Python
set(DISTRO_TAG "" CACHE STRING "distribution suffix appended to the package version")
configure_file("${PROJECT_SOURCE_DIR}/HsmToPythonPackOptions.cmake.in"
               "${PROJECT_BINARY_DIR}/HsmToPythonPackOptions.cmake"
               @ONLY)
set(CPACK_PROJECT_CONFIG_FILE "${PROJECT_BINARY_DIR}/HsmToPythonPackOptions.cmake")

include(CPack)
