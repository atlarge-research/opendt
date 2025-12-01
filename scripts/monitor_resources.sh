#!/bin/bash
# OpenDT Resource Monitoring Script
# Usage: ./scripts/monitor_resources.sh

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

while true; do
  clear
  echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║         OpenDT Resource Monitor (M1 Max)              ║${NC}"
  echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
  echo ""
  
  echo -e "${YELLOW}=== Docker Container Stats ===${NC}"
  docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.PIDs}}"
  echo ""
  
  echo -e "${YELLOW}=== OpenDC Process Count ===${NC}"
  CALIB_PROC=$(docker exec opendt-calibrator ps aux 2>/dev/null | grep -c "OpenDCExperimentRunner" || echo "0")
  SIM_PROC=$(docker exec opendt-simulator ps aux 2>/dev/null | grep -c "OpenDCExperimentRunner" || echo "0")
  
  echo -e "Calibrator OpenDC processes: ${CALIB_PROC}"
  echo -e "Simulator OpenDC processes:  ${SIM_PROC}"
  echo -e "Total OpenDC processes:      $((CALIB_PROC + SIM_PROC))"
  
  if [ $((CALIB_PROC + SIM_PROC)) -gt 4 ]; then
    echo -e "${RED}⚠️  HIGH PROCESS COUNT - May cause CPU contention${NC}"
  fi
  echo ""
  
  echo -e "${YELLOW}=== Java Process Details ===${NC}"
  echo "Calibrator Java processes:"
  docker exec opendt-calibrator ps aux 2>/dev/null | grep "java" | grep -v grep | awk '{print $2, $3, $4, $11}' || echo "None"
  echo ""
  echo "Simulator Java processes:"
  docker exec opendt-simulator ps aux 2>/dev/null | grep "java" | grep -v grep | awk '{print $2, $3, $4, $11}' || echo "None"
  echo ""
  
  echo -e "${YELLOW}=== System Info ===${NC}"
  echo "Host CPU cores: $(sysctl -n hw.ncpu 2>/dev/null || echo "Unknown")"
  echo "Docker Memory Limit: 7.654 GiB"
  echo ""
  
  echo -e "${YELLOW}=== Recent Logs ===${NC}"
  echo "Last calibrator activity:"
  docker logs opendt-calibrator 2>&1 | grep -E "(Starting calibration|drift|complete)" | tail -3
  echo ""
  echo "Last simulator activity:"
  docker logs opendt-simulator 2>&1 | grep -E "(Starting simulation|cached|complete)" | tail -3
  echo ""
  
  echo -e "${GREEN}Press Ctrl+C to exit | Refreshing every 3 seconds...${NC}"
  sleep 3
done
