Feature: Gestion des lots de café
  En tant que gestionnaire FutureKawa
  Je veux créer et consulter des lots de café
  Afin de tracer les stocks par pays et entrepôt

  Scenario: Créer un nouveau lot
    Given l'API FutureKawa est démarrée
    When je crée un lot avec lot_id "LOT-BR-001", pays "Brésil", exploitation "Fazenda São João", entrepot "Entrepôt A"
    Then la réponse a le statut 201
    And le lot "LOT-BR-001" est bien enregistré

  Scenario: Refuser un lot avec lot_id dupliqué
    Given l'API FutureKawa est démarrée
    And le lot "LOT-BR-002" existe déjà en base
    When je crée un lot avec lot_id "LOT-BR-002", pays "Brésil", exploitation "Fazenda São João", entrepot "Entrepôt A"
    Then la réponse a le statut 409

  Scenario: Lister les lots existants
    Given l'API FutureKawa est démarrée
    And le lot "LOT-EC-001" existe déjà en base
    When je consulte la liste des lots
    Then la réponse a le statut 200
    And la liste contient au moins un lot
