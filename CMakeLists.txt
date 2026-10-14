cmake_minimum_required(VERSION 3.16)

# the Debian package of the generator, its commands and its editor plugin;
# nothing is compiled
project(hsm-to-python VERSION 2.0.0 LANGUAGES NONE)

# the place of the pure Python modules on Debian
set(PYTHON_INSTALL_DIR "lib/python3/dist-packages" CACHE STRING
    "the directory of the modules under the prefix")
# the system plugin folder of CyberiadaHSM-Editor
set(PLUGIN_INSTALL_DIR "share/cyberiada-editor/plugins/hsm-to-python")
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

install(FILES ${CMAKE_CURRENT_SOURCE_DIR}/ChangeLog.md
              ${CMAKE_CURRENT_SOURCE_DIR}/README.md
              ${CMAKE_CURRENT_SOURCE_DIR}/LICENSE
        DESTINATION ${DOC_INSTALL_DIR})

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
  add_test(NAME plugin
           COMMAND ${Python3_EXECUTABLE} -B plugin_test.py
           WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/test)
endif()

configure_file("${PROJECT_SOURCE_DIR}/HsmToPythonPackOptions.cmake.in"
               "${PROJECT_BINARY_DIR}/HsmToPythonPackOptions.cmake"
               @ONLY)
set(CPACK_PROJECT_CONFIG_FILE "${PROJECT_BINARY_DIR}/HsmToPythonPackOptions.cmake")

include(CPack)
