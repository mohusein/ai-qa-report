-- Run this once to set up the database.
-- mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS CallCenterQA;
USE CallCenterQA;

-- Agents table (optional — populate from your dialer)
CREATE TABLE IF NOT EXISTS Agents (
    agent_id   INT          PRIMARY KEY,
    full_name  VARCHAR(100),
    department VARCHAR(50)
);

-- Main QA evaluation table
CREATE TABLE IF NOT EXISTS CallEvaluations (
    evaluation_id       INT AUTO_INCREMENT PRIMARY KEY,
    call_uuid           VARCHAR(200) UNIQUE,          -- filename or dialer UUID
    agent_name          VARCHAR(100),
    agent_id            INT          DEFAULT NULL,
    lead_phone          VARCHAR(20),
    call_date           DATE,
    call_timestamp      DATETIME     DEFAULT CURRENT_TIMESTAMP,

    -- Telephony metadata (populated when processing audio files)
    duration_seconds    INT          DEFAULT NULL,
    hangup_source       VARCHAR(20)  DEFAULT NULL,    -- Agent | Customer | System
    transfer_destination VARCHAR(50) DEFAULT NULL,

    -- AI results
    detected_loan_type  VARCHAR(50)  DEFAULT NULL,
    category            VARCHAR(50)  DEFAULT NULL,    -- referral | cold call | follow up | no evaluation
    transcription_text  MEDIUMTEXT,
    qa_score            INT          DEFAULT NULL,
    qa_feedback         TEXT,
    qa_summary          TEXT,
    grading_json        JSON,                         -- full AI response

    FOREIGN KEY (agent_id) REFERENCES Agents(agent_id) ON DELETE SET NULL
);

-- Fast reporting indexes
CREATE INDEX IF NOT EXISTS idx_agent_score ON CallEvaluations(agent_name, qa_score);
CREATE INDEX IF NOT EXISTS idx_call_date   ON CallEvaluations(call_date);
