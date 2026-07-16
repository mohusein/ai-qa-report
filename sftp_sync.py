import json

from ingestion.sftp_connector import SFTPRecordingConnector


if __name__ == "__main__":
    with SFTPRecordingConnector() as connector:
        print(json.dumps(connector.sync_once(), indent=2))