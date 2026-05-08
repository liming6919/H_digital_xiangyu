cmake_minimum_required(VERSION 3.8)
project(ymbot_devices_driver)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(std_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

################################################
## Messages
################################################

# ROS2 Humble: 使用相对路径（相对于包目录）
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/MotorControl.msg"
  DEPENDENCIES std_msgs
)

###################################
## ROS2 ament package configuration
###################################

# 检测架构，选择 eu_planet 库路径
if(CMAKE_SYSTEM_PROCESSOR MATCHES "x86_64")
  set(EU_PLANET_LIB_PATH "${PROJECT_SOURCE_DIR}/lib_x86_64")
  message(STATUS "Using x86_64 eu_planet lib")
elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64")
  set(EU_PLANET_LIB_PATH "${PROJECT_SOURCE_DIR}/lib_ARM")
  message(STATUS "Using ARM eu_planet lib")
else()
  message(FATAL_ERROR "Unsupported architecture: ${CMAKE_SYSTEM_PROCESSOR}")
endif()

find_library(EU_PLANET_LIB eu_planet PATHS ${EU_PLANET_LIB_PATH})
if(NOT EU_PLANET_LIB)
  message(FATAL_ERROR "eu_planet library not found")
endif()

ament_export_include_directories(include)

###################################
## Build
###################################

include_directories(
  include
  include/ymbot_devices_driver
)

add_library(hand_inspire_api SHARED
  src/ymbot_hand_inspire_api.cpp
)

add_library(head_RTrobot_api SHARED
  src/ymbot_head_RTrobot_api.cpp
)

add_library(joint_eu_api SHARED
  src/ymbot_joint_eu_api.cpp
)
target_link_libraries(joint_eu_api
  ${EU_PLANET_LIB}
)

add_library(neck_dynamixel_api SHARED
  src/ymbot_neck_dynamixel_api.cpp
)


###################################
## Executables
###################################

add_executable(ymbot_joint_eu_keyboard_multiple_canables
  src/ymbot_joint_eu_keyboard_multiple_canables.cpp
  src/ymbot_joint_eu_api.cpp
)
target_include_directories(ymbot_joint_eu_keyboard_multiple_canables PRIVATE include)
target_link_libraries(ymbot_joint_eu_keyboard_multiple_canables
  ${EU_PLANET_LIB}
)

###################################
## Install
###################################

install(TARGETS
  hand_inspire_api
  head_RTrobot_api
  joint_eu_api
  neck_dynamixel_api
  ymbot_joint_eu_keyboard_multiple_canables
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

ament_export_libraries(
  hand_inspire_api
  head_RTrobot_api
  joint_eu_api
  neck_dynamixel_api
)

ament_package()
