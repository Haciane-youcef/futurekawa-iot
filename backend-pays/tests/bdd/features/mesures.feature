# language: fr
Feature: Gestion des mesures IoT
  En tant que système de monitoring FutureKawa
  Je veux enregistrer et consulter les mesures de température et humidité
  Afin de surveiller les conditions de stockage du café

  Scenario: Enregistrer une mesure valide
    Given l'API FutureKawa est démarrée
    When je soumets une mesure avec température 20.5 et humidité 60.0
    Then la réponse a le statut 201
    And la mesure est bien enregistrée en base

  Scenario: Refuser une mesure sans température
    Given l'API FutureKawa est démarrée
    When je soumets une mesure sans champ température
    Then la réponse a le statut 422

  Scenario: Lister les mesures enregistrées
    Given l'API FutureKawa est démarrée
    And au moins une mesure existe en base
    When je consulte la liste des mesures
    Then la réponse a le statut 200
    And la liste contient au moins une mesure
