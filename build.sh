#!/usr/bin/env bash
if [[ -n $1 ]]; then
  image_name=$1
else
  echo "Specify an image name in the first argument"
  exit 1
fi

names=("core" "latest" "sm" "api" "tbot")
dockerfiles=("docker/core/Dockerfile" "docker/antiintuit/Dockerfile" "docker/session-manager/Dockerfile" "docker/api/Dockerfile" "docker/tbot/Dockerfile")
contexts=("" "antiintuit/" "session-manager/" "" "tbot/")
builds_count=${#names[*]}

for ((i = 0; i < builds_count; i++)); do
  if [[ -z ${contexts[$i]} ]]; then
    docker build -t "$image_name:${names[$i]}" - < "${dockerfiles[$i]}"
  else
    docker build -t "$image_name:${names[$i]}" -f "${dockerfiles[$i]}" "${contexts[$i]}"
  fi
done

docker push "$image_name"