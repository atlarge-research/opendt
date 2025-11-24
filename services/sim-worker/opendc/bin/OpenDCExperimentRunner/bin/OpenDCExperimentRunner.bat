@rem
@rem Copyright 2015 the original author or authors.
@rem
@rem Licensed under the Apache License, Version 2.0 (the "License");
@rem you may not use this file except in compliance with the License.
@rem You may obtain a copy of the License at
@rem
@rem      https://www.apache.org/licenses/LICENSE-2.0
@rem
@rem Unless required by applicable law or agreed to in writing, software
@rem distributed under the License is distributed on an "AS IS" BASIS,
@rem WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
@rem See the License for the specific language governing permissions and
@rem limitations under the License.
@rem
@rem SPDX-License-Identifier: Apache-2.0
@rem

@if "%DEBUG%"=="" @echo off
@rem ##########################################################################
@rem
@rem  OpenDCExperimentRunner startup script for Windows
@rem
@rem ##########################################################################

@rem Set local scope for the variables with windows NT shell
if "%OS%"=="Windows_NT" setlocal

set DIRNAME=%~dp0
if "%DIRNAME%"=="" set DIRNAME=.
@rem This is normally unused
set APP_BASE_NAME=%~n0
set APP_HOME=%DIRNAME%..

@rem Resolve any "." and ".." in APP_HOME to make it shorter.
for %%i in ("%APP_HOME%") do set APP_HOME=%%~fi

@rem Add default JVM options here. You can also use JAVA_OPTS and OPEN_DC_EXPERIMENT_RUNNER_OPTS to pass JVM options to this script.
set DEFAULT_JVM_OPTS=

@rem Find java.exe
if defined JAVA_HOME goto findJavaFromJavaHome

set JAVA_EXE=java.exe
%JAVA_EXE% -version >NUL 2>&1
if %ERRORLEVEL% equ 0 goto execute

echo. 1>&2
echo ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH. 1>&2
echo. 1>&2
echo Please set the JAVA_HOME variable in your environment to match the 1>&2
echo location of your Java installation. 1>&2

goto fail

:findJavaFromJavaHome
set JAVA_HOME=%JAVA_HOME:"=%
set JAVA_EXE=%JAVA_HOME%/bin/java.exe

if exist "%JAVA_EXE%" goto execute

echo. 1>&2
echo ERROR: JAVA_HOME is set to an invalid directory: %JAVA_HOME% 1>&2
echo. 1>&2
echo Please set the JAVA_HOME variable in your environment to match the 1>&2
echo location of your Java installation. 1>&2

goto fail

:execute
@rem Setup the command line

set CLASSPATH=%APP_HOME%\lib\opendc-experiments-base.jar;%APP_HOME%\lib\opendc-compute-failure.jar;%APP_HOME%\lib\opendc-compute-simulator.jar;%APP_HOME%\lib\opendc-compute-workload.jar;%APP_HOME%\lib\opendc-compute-topology.jar;%APP_HOME%\lib\opendc-compute-carbon.jar;%APP_HOME%\lib\opendc-compute-api.jar;%APP_HOME%\lib\opendc-simulator-compute.jar;%APP_HOME%\lib\opendc-simulator-core.jar;%APP_HOME%\lib\opendc-trace-api.jar;%APP_HOME%\lib\opendc-trace-parquet.jar;%APP_HOME%\lib\opendc-simulator-flow.jar;%APP_HOME%\lib\opendc-common.jar;%APP_HOME%\lib\kotlinx-serialization-core-jvm-1.6.0.jar;%APP_HOME%\lib\kotlinx-serialization-json-jvm-1.6.0.jar;%APP_HOME%\lib\clikt-jvm-3.5.2.jar;%APP_HOME%\lib\kotlin-logging-jvm-3.0.5.jar;%APP_HOME%\lib\kotlin-stdlib-jdk8-1.8.10.jar;%APP_HOME%\lib\jackson-dataformat-csv-2.16.1.jar;%APP_HOME%\lib\hadoop-common-3.3.6.jar;%APP_HOME%\lib\jackson-databind-2.16.1.jar;%APP_HOME%\lib\jackson-annotations-2.16.1.jar;%APP_HOME%\lib\jackson-core-2.16.1.jar;%APP_HOME%\lib\jackson-module-kotlin-2.16.1.jar;%APP_HOME%\lib\kotlin-reflect-1.6.21.jar;%APP_HOME%\lib\kotlinx-coroutines-core-jvm-1.8.1.jar;%APP_HOME%\lib\kotlin-stdlib-jdk7-1.8.10.jar;%APP_HOME%\lib\kotlin-stdlib-1.9.22.jar;%APP_HOME%\lib\progressbar-0.10.0.jar;%APP_HOME%\lib\log4j-slf4j2-impl-2.23.0.jar;%APP_HOME%\lib\log4j-core-2.23.0.jar;%APP_HOME%\lib\commons-math3-3.6.1.jar;%APP_HOME%\lib\microprofile-config-api-3.1.jar;%APP_HOME%\lib\annotations-23.0.0.jar;%APP_HOME%\lib\jline-3.23.0.jar;%APP_HOME%\lib\log4j-api-2.23.0.jar;%APP_HOME%\lib\parquet-hadoop-1.13.1.jar;%APP_HOME%\lib\parquet-column-1.13.1.jar;%APP_HOME%\lib\parquet-encoding-1.13.1.jar;%APP_HOME%\lib\parquet-common-1.13.1.jar;%APP_HOME%\lib\metrics-core-3.2.4.jar;%APP_HOME%\lib\slf4j-api-2.0.9.jar;%APP_HOME%\lib\hadoop-mapreduce-client-core-3.3.6.jar;%APP_HOME%\lib\parquet-format-structures-1.13.1.jar;%APP_HOME%\lib\parquet-jackson-1.13.1.jar;%APP_HOME%\lib\snappy-java-1.1.8.3.jar;%APP_HOME%\lib\aircompressor-0.21.jar;%APP_HOME%\lib\commons-pool-1.6.jar;%APP_HOME%\lib\zstd-jni-1.5.0-1.jar;%APP_HOME%\lib\audience-annotations-0.13.0.jar;%APP_HOME%\lib\hadoop-shaded-protobuf_3_7-1.1.1.jar;%APP_HOME%\lib\hadoop-shaded-guava-1.1.1.jar;%APP_HOME%\lib\guava-27.0-jre.jar;%APP_HOME%\lib\commons-codec-1.15.jar;%APP_HOME%\lib\commons-io-2.8.0.jar;%APP_HOME%\lib\commons-net-3.9.0.jar;%APP_HOME%\lib\commons-beanutils-1.9.4.jar;%APP_HOME%\lib\commons-collections-3.2.2.jar;%APP_HOME%\lib\jakarta.activation-api-1.2.1.jar;%APP_HOME%\lib\jersey-json-1.20.jar;%APP_HOME%\lib\commons-configuration2-2.8.0.jar;%APP_HOME%\lib\commons-logging-1.2.jar;%APP_HOME%\lib\commons-text-1.10.0.jar;%APP_HOME%\lib\commons-lang3-3.12.0.jar;%APP_HOME%\lib\re2j-1.1.jar;%APP_HOME%\lib\protobuf-java-2.5.0.jar;%APP_HOME%\lib\jsr305-3.0.2.jar;%APP_HOME%\lib\commons-compress-1.21.jar;%APP_HOME%\lib\woodstox-core-5.4.0.jar;%APP_HOME%\lib\stax2-api-4.2.1.jar;%APP_HOME%\lib\failureaccess-1.0.jar;%APP_HOME%\lib\listenablefuture-9999.0-empty-to-avoid-conflict-with-guava.jar;%APP_HOME%\lib\checker-qual-2.5.2.jar;%APP_HOME%\lib\j2objc-annotations-1.1.jar;%APP_HOME%\lib\animal-sniffer-annotations-1.17.jar;%APP_HOME%\lib\jettison-1.1.jar;%APP_HOME%\lib\jaxb-impl-2.2.3-1.jar;%APP_HOME%\lib\jaxb-api-2.2.2.jar;%APP_HOME%\lib\stax-api-1.0-2.jar;%APP_HOME%\lib\activation-1.1.jar


@rem Execute OpenDCExperimentRunner
"%JAVA_EXE%" %DEFAULT_JVM_OPTS% %JAVA_OPTS% %OPEN_DC_EXPERIMENT_RUNNER_OPTS%  -classpath "%CLASSPATH%" org.opendc.experiments.base.runner.ExperimentCli %*

:end
@rem End local scope for the variables with windows NT shell
if %ERRORLEVEL% equ 0 goto mainEnd

:fail
rem Set variable OPEN_DC_EXPERIMENT_RUNNER_EXIT_CONSOLE if you need the _script_ return code instead of
rem the _cmd.exe /c_ return code!
set EXIT_CODE=%ERRORLEVEL%
if %EXIT_CODE% equ 0 set EXIT_CODE=1
if not ""=="%OPEN_DC_EXPERIMENT_RUNNER_EXIT_CONSOLE%" exit %EXIT_CODE%
exit /b %EXIT_CODE%

:mainEnd
if "%OS%"=="Windows_NT" endlocal

:omega
