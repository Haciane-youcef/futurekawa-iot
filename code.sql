-- CONFIG
INSERT INTO config (pays, temp_ideale, hum_ideale, tolerance_temp, tolerance_hum, email_destinataire, intervalle_verification)
VALUES ('bresil', 29.0, 55.0, 3.0, 2.0, 'responsable.bresil@futurekawa.com', 3600);

-- EXPLOITATIONS
INSERT INTO exploitation (nom, id_config) VALUES
('Fazenda Santos', 1),
('Fazenda Rio', 1);

-- ENTREPOTS
INSERT INTO entrepot (nom, localisation, id_exploitation) VALUES
('Entrepot Santos Centre', 'Santos, Sao Paulo, Bresil', 1),
('Entrepot Santos Port',   'Port de Santos, Bresil',     1),
('Entrepot Rio Sud',       'Rio de Janeiro, Bresil',      2);

-- ROLES
INSERT INTO role (libelle, description) VALUES
('responsable_exploitation', 'Gestion des lots et entrepots de son exploitation'),
('responsable_entrepot',     'Creation et modification des lots de son entrepot'),
('qualite_local',            'Consultation alertes et mesures du pays'),
('correspondant_si',         'Support technique niveau 1, relais terrain');

-- UTILISATEURS
INSERT INTO utilisateur (nom, prenom, email, mot_de_passe, actif) VALUES
('Silva',  'Carlos', 'carlos.silva@futurekawa.com',  'pbkdf2:sha256:hash_carlos',  TRUE),
('Santos', 'Maria',  'maria.santos@futurekawa.com',  'pbkdf2:sha256:hash_maria',   TRUE),
('Lima',   'Pedro',  'pedro.lima@futurekawa.com',    'pbkdf2:sha256:hash_pedro',   TRUE),
('Tech',   'Ana',    'ana.tech@futurekawa.com',      'pbkdf2:sha256:hash_ana',     TRUE);

-- UTILISATEUR_ROLE
INSERT INTO utilisateur_role (id_utilisateur, id_role) VALUES
(1, 1),
(2, 2),
(3, 1),
(3, 2),
(4, 4);

-- UTILISATEUR_EXPLOITATION
INSERT INTO utilisateur_exploitation (id_utilisateur, id_exploitation, date_debut, date_fin) VALUES
(1, 1, '2024-03-15 00:00:00', NULL),
(3, 2, '2024-01-10 00:00:00', NULL);

-- UTILISATEUR_ENTREPOT
INSERT INTO utilisateur_entrepot (id_utilisateur, id_entrepot, date_debut, date_fin) VALUES
(2, 1, '2024-01-10 00:00:00', NULL),
(3, 3, '2024-01-10 00:00:00', NULL);

-- CAPTEURS
INSERT INTO capteur (type_capteur, reference, statut, id_entrepot) VALUES
('DHT22', 'DHT22-SANTOS-01', 'actif', 1),
('DHT22', 'DHT22-SANTOS-02', 'actif', 2),
('DHT22', 'DHT22-RIO-01',    'actif', 3);

-- MESURES
INSERT INTO mesure (temperature, humidite, date_mesure, id_capteur) VALUES
(29.5, 55.2, NOW() - INTERVAL '9 hours', 1),
(35.0, 48.0, NOW() - INTERVAL '8 hours', 1),
(28.0, 82.0, NOW() - INTERVAL '7 hours', 1),
(28.5, 54.8, NOW() - INTERVAL '6 hours', 1),
(27.3, 56.1, NOW() - INTERVAL '5 hours', 2),
(30.1, 55.0, NOW() - INTERVAL '4 hours', 2),
(31.8, 53.5, NOW() - INTERVAL '3 hours', 2),
(29.0, 55.5, NOW() - INTERVAL '2 hours', 3),
(26.5, 57.0, NOW() - INTERVAL '1 hour',  3);

-- LOTS
INSERT INTO lot (id_lot, date_stockage, statut, id_entrepot, id_utilisateur) VALUES
('BRESIL-2024-001', '2023-01-15 10:00:00', 'conforme', 1, 1),
('BRESIL-2024-002', '2024-06-20 14:00:00', 'conforme', 1, 1),
('BRESIL-2024-003', '2024-11-05 09:00:00', 'conforme', 3, 3);

-- ALERTES MESURES
INSERT INTO alerte_mesure (type_alerte, message, valeur_mesuree, seuil_min, seuil_max, date_alerte, statut, id_mesure) VALUES
('temperature', 'Temperature anormale : 35.0C (ideal: 29.0C +/- 3.0C)', 35.0, 26.0, 32.0, NOW() - INTERVAL '8 hours', 'non_lue', 2),
('humidite',    'Humidite anormale : 48.0% (ideal: 55.0% +/- 2.0%)',    48.0, 53.0, 57.0, NOW() - INTERVAL '8 hours', 'non_lue', 2),
('humidite',    'Humidite anormale : 82.0% (ideal: 55.0% +/- 2.0%)',    82.0, 53.0, 57.0, NOW() - INTERVAL '7 hours', 'lue',     3);

-- ALERTES LOTS
INSERT INTO alerte_lot (message, date_alerte, statut, id_lot) VALUES
('Lot BRESIL-2024-001 perime - stocke depuis 2023-01-15', NOW(), 'non_lue', 'BRESIL-2024-001');