QTRAN-main/
├── src/
│   ├── FeatureKnowledgeBaseConstruction/
│   │   ├── NoSQL/                          [新增]
│   │   │   ├── MongoDB/                    [新增]
│   │   │   ├── Redis/                      [新增]
│   │   │   ├── Neo4j/                      [新增]
│   │   │   └── Cassandra/                  [新增]
│   │   └── ... (原有 RDBMS 目录)
│   ├── Tools/
│   │   ├── DatabaseConnect/
│   │   │   └── database_connector.py       [修改]
│   │   └── OracleChecker/
│   │       ├── oracle_check.py
│   │       └── oracle_check_nosql.py       [新增]
│   └── ... (其他模块保持不变)
├── RAG_Feature_Mapping/
│   ├── NoSQL/                              [新增]
│   └── ... (原有 RDBMS 目录)
├── MutationData/
│   ├── FineTuningTrainingData/
│   │   ├── NoSQL/                          [新增]
│   │   └── ...
│   └── MutationLLMPrompt/
│       ├── NoSQL/                          [新增]
│       └── ...
└── ...