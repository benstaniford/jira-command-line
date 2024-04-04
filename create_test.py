#!/usr/bin/python

import requests
import json
import sys


def create_tickets(feature_file_path, label):
    body = {
        "client_id": "bstaniford@beyondtrust.com",
        "client_secret": "ATATT3xFfGF0tuq7Cw-PEngTONZAHLo1D4lcQ1d2vEC-jz87W2CR40pTpmIgdbuYpOailudyUateOyhi2V67PvE1ye4hG5O730ZofMcWlcJhAiSaQCelJ0nkHWBSnrrStO9iF7WbzwyBdIev9Zq2BJLQplngYX4Dd9A5DripgnesE4wnXFGWfhI=C79DF34B",
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    response = requests.post(
        "https://xray.cloud.getxray.app/api/v1/authenticate", headers=headers, json=body
    )

    if response.status_code != 200:
        print(f"Auth error {response.status_code}.")
        sys.exit()

    access_token = response.text.strip("'\"")

    headers_with_token = {
        "Authorization": f"Bearer {access_token}",
    }

    custom_fields = {
        "fields": {
            "customfield_10001": "e4e9e450-7523-478b-bccd-06ce6f7419ec-14",
            "customfield_10108": {"value": "PM Mac"},
            "components": [{"name": label}],
        }
    }

    # Prepare the files for the feature import request
    files = {
        "file": ("feature_file.feature", open(feature_file_path, "rb")),
        "testInfo": ("testInfo.json", json.dumps(custom_fields), "application/json"),
    }

    # Make the feature import request
    feature_import_url = (
        "https://xray.cloud.getxray.app/api/v2/import/feature?projectKey=EPM"
    )

    feature_import_response = requests.post(
        feature_import_url, headers=headers_with_token, files=files
    )

    if feature_import_response.status_code != 200:
        print(f"Error on {feature_file_path}.")
        sys.exit()

    print(f"Successfully generated events for {feature_file_path}.")


#csv_file_path = "C:\\Users\\jmunro\\OneDrive - BeyondTrust Corporation\\Documents\\Scripts\\Python\\FeatureFiles.csv"
#df = pd.read_csv(csv_file_path)

#file_label_mapping = dict(zip(df["Name"], df["Label"]))

#for file_name, label in file_label_mapping.items():
create_tickets("", "Test")

