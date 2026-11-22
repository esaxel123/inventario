-- init.sql — Sistema de Inventario Tecnológico
-- Organización: Creation Technologies (taller de electrónica)
-- Generado a partir del respaldo real del equipo (2026-11-21).
-- Se ejecuta SOLO la primera vez, cuando el volumen de MySQL
-- esta vacio (docker-entrypoint-initdb.d).
-- Correcciones frente al respaldo original:
--  * Eliminado el duplicado id 195 'Optoacoplador PC817'
--    (sin inventario ni historial). Se conserva id 126.
--  * componentes: + categoria, + descripcion, + estado.
--  * inventario: + stock_minimo (10 por defecto).
--  * empleados.contrasena ahora guarda un hash PBKDF2.
--  * Nueva tabla eventos_nfc (eventos del lector NFC).
--  * Corregidos los parentesis de apertura de la primera fila de
--    los INSERT de pedidos e historial_pedidos (faltaban y MySQL
--    rechazaba todo el script de inicializacion).
-- Usuario inicial: Jimmy (CEO, supervisor), NFC 698A00F4,
-- contrasena temporal 'Temporal123' (cambiarla al entrar).

USE inventario_ct;

-- Forzar UTF-8 en la importación: sin esto, el cliente de MySQL puede
-- leer el archivo como latin1 y los acentos quedan doble codificados
-- en la base (por ejemplo, 'Batería' se guarda como 'BaterÃ­a').
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS componentes (
  id_componente INT NOT NULL AUTO_INCREMENT,
  nombre VARCHAR(50) NOT NULL,
  categoria VARCHAR(40) DEFAULT NULL,
  descripcion VARCHAR(120) DEFAULT NULL,
  estado ENUM('activo','fuera_de_servicio')
    NOT NULL DEFAULT 'activo',
  PRIMARY KEY (id_componente),
  UNIQUE KEY componentes (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS empleados (
  id_empleado INT NOT NULL AUTO_INCREMENT,
  nombre VARCHAR(40) NOT NULL,
  puesto VARCHAR(20) DEFAULT NULL,
  nfc_id VARCHAR(30) DEFAULT NULL,
  contrasena VARCHAR(200) NOT NULL,
  PRIMARY KEY (id_empleado),
  UNIQUE KEY empleado (nfc_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS inventario (
  id_inventario INT NOT NULL AUTO_INCREMENT,
  id_componente INT NOT NULL,
  cantidad INT NOT NULL DEFAULT 0,
  ubicacion VARCHAR(10) NOT NULL,
  precio DECIMAL(10,2) DEFAULT NULL,
  stock_minimo INT NOT NULL DEFAULT 10,
  PRIMARY KEY (id_inventario),
  KEY id_componente (id_componente),
  CONSTRAINT inventario_ibfk_1 FOREIGN KEY (id_componente)
    REFERENCES componentes (id_componente)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS pedidos (
  id_pedido INT NOT NULL AUTO_INCREMENT,
  id_empleado INT NOT NULL,
  fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  estado ENUM('pendiente','cancelado','completado','retirado')
    DEFAULT 'pendiente',
  comentarios TEXT,
  PRIMARY KEY (id_pedido),
  KEY idx_empleado_estado (id_empleado, estado),
  CONSTRAINT fk_pedido_empleado FOREIGN KEY (id_empleado)
    REFERENCES empleados (id_empleado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS historial_pedidos (
  id_historial INT NOT NULL AUTO_INCREMENT,
  id_componente INT NOT NULL,
  id_empleado INT NOT NULL,
  cantidad INT NOT NULL,
  fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  recibido TINYINT(1) NOT NULL,
  id_pedido INT NOT NULL,
  PRIMARY KEY (id_historial),
  KEY id_componente (id_componente),
  KEY fk_empleado (id_empleado),
  KEY idx_id_pedido (id_pedido),
  CONSTRAINT fk_empleado FOREIGN KEY (id_empleado)
    REFERENCES empleados (id_empleado),
  CONSTRAINT fk_historial_pedido FOREIGN KEY (id_pedido)
    REFERENCES pedidos (id_pedido),
  CONSTRAINT historial_pedidos_ibfk_1 FOREIGN KEY (id_componente)
    REFERENCES componentes (id_componente)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS eventos_nfc (
  id INT NOT NULL AUTO_INCREMENT,
  tipo VARCHAR(30) NOT NULL,
  nfc_id VARCHAR(30) DEFAULT NULL,
  id_empleado INT DEFAULT NULL,
  detalle JSON DEFAULT NULL,
  fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_tipo_fecha (tipo, fecha_hora),
  CONSTRAINT fk_evento_empleado FOREIGN KEY (id_empleado)
    REFERENCES empleados (id_empleado)
    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

INSERT INTO componentes
  (id_componente, nombre, categoria, descripcion, estado)
VALUES
(128,'74HC04 inversor logico','Circuito integrado',NULL,'activo'),
(129,'74HC08 compuerta AND','Circuito integrado',NULL,'activo'),
(127,'74HC595 registro de desplazamiento','Circuito integrado',NULL,'activo'),
(200,'Bateria CR2032','Batería',NULL,'activo'),
(191,'Bobina 1 mH','Bobina / Inductor',NULL,'activo'),
(168,'Bornera 2 pines','Conector',NULL,'activo'),
(169,'Bornera 3 pines','Conector',NULL,'activo'),
(180,'Buzzer activo 5V','Buzzer',NULL,'activo'),
(181,'Buzzer pasivo 5V','Buzzer',NULL,'activo'),
(49,'Capacitor ceramico 1 nF','Capacitor',NULL,'activo'),
(53,'Capacitor ceramico 1 uF','Capacitor',NULL,'activo'),
(50,'Capacitor ceramico 10 nF','Capacitor',NULL,'activo'),
(45,'Capacitor ceramico 10 pF','Capacitor',NULL,'activo'),
(54,'Capacitor ceramico 10 uF','Capacitor',NULL,'activo'),
(51,'Capacitor ceramico 100 nF','Capacitor',NULL,'activo'),
(48,'Capacitor ceramico 100 pF','Capacitor',NULL,'activo'),
(46,'Capacitor ceramico 22 pF','Capacitor',NULL,'activo'),
(52,'Capacitor ceramico 220 nF','Capacitor',NULL,'activo'),
(47,'Capacitor ceramico 47 pF','Capacitor',NULL,'activo'),
(68,'Capacitor de poliester 1 uF','Capacitor',NULL,'activo'),
(65,'Capacitor de poliester 100 nF','Capacitor',NULL,'activo'),
(66,'Capacitor de poliester 220 nF','Capacitor',NULL,'activo'),
(67,'Capacitor de poliester 470 nF','Capacitor',NULL,'activo'),
(69,'Capacitor de polipropileno 100 nF','Capacitor',NULL,'activo'),
(55,'Capacitor electrolitico 1 uF 16V','Capacitor',NULL,'activo'),
(56,'Capacitor electrolitico 10 uF 16V','Capacitor',NULL,'activo'),
(59,'Capacitor electrolitico 100 uF 16V','Capacitor',NULL,'activo'),
(62,'Capacitor electrolitico 1000 uF 25V','Capacitor',NULL,'activo'),
(57,'Capacitor electrolitico 22 uF 25V','Capacitor',NULL,'activo'),
(60,'Capacitor electrolitico 220 uF 25V','Capacitor',NULL,'activo'),
(63,'Capacitor electrolitico 2200 uF 25V','Capacitor',NULL,'activo'),
(58,'Capacitor electrolitico 47 uF 25V','Capacitor',NULL,'activo'),
(61,'Capacitor electrolitico 470 uF 25V','Capacitor',NULL,'activo'),
(64,'Capacitor electrolitico 4700 uF 50V','Capacitor',NULL,'activo'),
(131,'CD4017 contador decimal','Circuito integrado',NULL,'activo'),
(132,'CD4047 multivibrador','Circuito integrado',NULL,'activo'),
(172,'Conector DC Jack 5.5mm','Conector',NULL,'activo'),
(176,'Conector Dupont hembra','Conector',NULL,'activo'),
(175,'Conector Dupont macho','Conector',NULL,'activo'),
(170,'Conector JST XH 2 pines','Conector',NULL,'activo'),
(171,'Conector JST XH 3 pines','Conector',NULL,'activo'),
(173,'Conector USB tipo A','Conector',NULL,'activo'),
(174,'Conector USB tipo C','Conector',NULL,'activo'),
(142,'Convertidor boost MT3608','Convertidor',NULL,'activo'),
(141,'Convertidor buck LM2596','Convertidor',NULL,'activo'),
(178,'Cristal oscilador 16 MHz','Cristal oscilador',NULL,'activo'),
(179,'Cristal oscilador 20 MHz','Cristal oscilador',NULL,'activo'),
(177,'Cristal oscilador 8 MHz','Cristal oscilador',NULL,'activo'),
(74,'Diodo de señal 1N4148','Diodo',NULL,'activo'),
(70,'Diodo rectificador 1N4001','Diodo',NULL,'activo'),
(71,'Diodo rectificador 1N4004','Diodo',NULL,'activo'),
(72,'Diodo rectificador 1N4007','Diodo',NULL,'activo'),
(73,'Diodo rectificador 1N5408','Diodo',NULL,'activo'),
(75,'Diodo Schottky 1N5819','Diodo',NULL,'activo'),
(76,'Diodo Schottky SS14','Diodo',NULL,'activo'),
(80,'Diodo Zener 12V','Diodo',NULL,'activo'),
(81,'Diodo Zener 24V','Diodo',NULL,'activo'),
(77,'Diodo Zener 3.3V','Diodo',NULL,'activo'),
(78,'Diodo Zener 5.1V','Diodo',NULL,'activo'),
(79,'Diodo Zener 6.2V','Diodo',NULL,'activo'),
(165,'Final de carrera','Interruptor',NULL,'activo'),
(186,'Fusible 1 A','Fusible',NULL,'activo'),
(187,'Fusible 2 A','Fusible',NULL,'activo'),
(188,'Fusible 5 A','Fusible',NULL,'activo'),
(185,'Fusible 500 mA','Fusible',NULL,'activo'),
(167,'Header hembra 1x40 pines','Conector',NULL,'activo'),
(166,'Header macho 1x40 pines','Conector',NULL,'activo'),
(189,'Inductor 10 uH','Bobina / Inductor',NULL,'activo'),
(190,'Inductor 100 uH','Bobina / Inductor',NULL,'activo'),
(163,'Interruptor DIP 4 posiciones','Interruptor',NULL,'activo'),
(164,'Interruptor DIP 8 posiciones','Interruptor',NULL,'activo'),
(161,'Interruptor DPDT','Interruptor',NULL,'activo'),
(160,'Interruptor SPDT','Interruptor',NULL,'activo'),
(159,'Interruptor SPST','Interruptor',NULL,'activo'),
(123,'L293D driver de motores','Motor',NULL,'activo'),
(124,'L298N driver de motores','Motor',NULL,'activo'),
(90,'LED amarillo 5mm','LED',NULL,'activo'),
(88,'LED azul 3mm','LED',NULL,'activo'),
(89,'LED azul 5mm','LED',NULL,'activo'),
(91,'LED blanco 5mm','LED',NULL,'activo'),
(97,'LED de alta potencia 1W blanco','LED',NULL,'activo'),
(93,'LED infrarrojo','LED',NULL,'activo'),
(92,'LED RGB 5mm','LED',NULL,'activo'),
(84,'LED rojo 3mm','LED',NULL,'activo'),
(85,'LED rojo 5mm','LED',NULL,'activo'),
(96,'LED SMD 0805 azul','LED',NULL,'activo'),
(94,'LED SMD 0805 rojo','LED',NULL,'activo'),
(95,'LED SMD 0805 verde','LED',NULL,'activo'),
(86,'LED verde 3mm','LED',NULL,'activo'),
(87,'LED verde 5mm','LED',NULL,'activo'),
(119,'LM324 amplificador operacional','Circuito integrado',NULL,'activo'),
(118,'LM358 amplificador operacional','Circuito integrado',NULL,'activo'),
(122,'LM386 amplificador de audio','Circuito integrado',NULL,'activo'),
(121,'LM393 comparador','Circuito integrado',NULL,'activo'),
(120,'LM741 amplificador operacional','Circuito integrado',NULL,'activo'),
(162,'Microinterruptor','Interruptor',NULL,'activo'),
(112,'MOSFET canal N 2N7000','MOSFET',NULL,'activo'),
(115,'MOSFET canal N AO3400A','MOSFET',NULL,'activo'),
(111,'MOSFET canal N IRF540N','MOSFET',NULL,'activo'),
(109,'MOSFET canal N IRFZ44N','MOSFET',NULL,'activo'),
(110,'MOSFET canal N IRLZ44N','MOSFET',NULL,'activo'),
(114,'MOSFET canal P IRF4905','MOSFET',NULL,'activo'),
(113,'MOSFET canal P IRF9540N','MOSFET',NULL,'activo'),
(197,'Motor DC 12V','Motor',NULL,'activo'),
(196,'Motor DC 3V-6V','Motor',NULL,'activo'),
(198,'Motor paso a paso 28BYJ-48','Motor',NULL,'activo'),
(116,'NE555 temporizador','Circuito integrado',NULL,'activo'),
(117,'NE556 doble temporizador','Circuito integrado',NULL,'activo'),
(126,'PC817 optoacoplador','Circuito integrado',NULL,'activo'),
(201,'Portapilas AA','Batería',NULL,'activo'),
(36,'Potenciometro 1 KOhm','Potenciómetro',NULL,'activo'),
(41,'Potenciometro 1 MOhm','Potenciómetro',NULL,'activo'),
(37,'Potenciometro 10 KOhms','Potenciómetro',NULL,'activo'),
(39,'Potenciometro 100 KOhms','Potenciómetro',NULL,'activo'),
(38,'Potenciometro 50 KOhms','Potenciómetro',NULL,'activo'),
(40,'Potenciometro 500 KOhms','Potenciómetro',NULL,'activo'),
(202,'Protoboard 400 puntos','Protoboard',NULL,'activo'),
(203,'Protoboard 830 puntos','Protoboard',NULL,'activo'),
(82,'Puente rectificador DB107','Rectificador',NULL,'activo'),
(83,'Puente rectificador KBPC5010','Rectificador',NULL,'activo'),
(157,'Pulsador normalmente abierto','Interruptor',NULL,'activo'),
(158,'Pulsador normalmente cerrado','Interruptor',NULL,'activo'),
(133,'Regulador 7805 5V','Regulador',NULL,'activo'),
(134,'Regulador 7809 9V','Regulador',NULL,'activo'),
(135,'Regulador 7812 12V','Regulador',NULL,'activo'),
(136,'Regulador 7815 15V','Regulador',NULL,'activo'),
(139,'Regulador AMS1117 3.3V','Regulador',NULL,'activo'),
(140,'Regulador AMS1117 5V','Regulador',NULL,'activo'),
(137,'Regulador LM317 ajustable','Regulador',NULL,'activo'),
(138,'Regulador LM337 ajustable negativo','Regulador',NULL,'activo'),
(183,'Relevador 12V 1 canal','Relevador',NULL,'activo'),
(182,'Relevador 5V 1 canal','Relevador',NULL,'activo'),
(184,'Relevador 5V 2 canales','Relevador',NULL,'activo'),
(44,'Reostato 100 Ohms','Potenciómetro',NULL,'activo'),
(6,'Resistencia 0 Ohms','Resistencia',NULL,'activo'),
(18,'Resistencia 1 KOhm','Resistencia',NULL,'activo'),
(30,'Resistencia 1 MOhm','Resistencia',NULL,'activo'),
(7,'Resistencia 1 Ohm','Resistencia',NULL,'activo'),
(19,'Resistencia 1.5 KOhms','Resistencia',NULL,'activo'),
(24,'Resistencia 10 KOhms','Resistencia',NULL,'activo'),
(31,'Resistencia 10 MOhms','Resistencia',NULL,'activo'),
(9,'Resistencia 10 Ohms','Resistencia',NULL,'activo'),
(27,'Resistencia 100 KOhms','Resistencia',NULL,'activo'),
(12,'Resistencia 100 Ohms','Resistencia',NULL,'activo'),
(13,'Resistencia 150 Ohms','Resistencia',NULL,'activo'),
(20,'Resistencia 2.2 KOhms','Resistencia',NULL,'activo'),
(25,'Resistencia 22 KOhms','Resistencia',NULL,'activo'),
(10,'Resistencia 22 Ohms','Resistencia',NULL,'activo'),
(28,'Resistencia 220 KOhms','Resistencia',NULL,'activo'),
(14,'Resistencia 220 Ohms','Resistencia',NULL,'activo'),
(21,'Resistencia 3.3 KOhms','Resistencia',NULL,'activo'),
(15,'Resistencia 330 Ohms','Resistencia',NULL,'activo'),
(22,'Resistencia 4.7 KOhms','Resistencia',NULL,'activo'),
(8,'Resistencia 4.7 Ohms','Resistencia',NULL,'activo'),
(26,'Resistencia 47 KOhms','Resistencia',NULL,'activo'),
(11,'Resistencia 47 Ohms','Resistencia',NULL,'activo'),
(29,'Resistencia 470 KOhms','Resistencia',NULL,'activo'),
(16,'Resistencia 470 Ohms','Resistencia',NULL,'activo'),
(23,'Resistencia 6.8 KOhms','Resistencia',NULL,'activo'),
(17,'Resistencia 680 Ohms','Resistencia',NULL,'activo'),
(35,'Resistencia de potencia 10W 10 Ohms','Resistencia',NULL,'activo'),
(34,'Resistencia de potencia 5W 100 Ohms','Resistencia',NULL,'activo'),
(32,'Resistencia SMD 1 KOhm','Resistencia',NULL,'activo'),
(33,'Resistencia SMD 10 KOhms','Resistencia',NULL,'activo'),
(155,'Sensor de corriente ACS712','Sensor',NULL,'activo'),
(153,'Sensor de efecto Hall A3144','Sensor',NULL,'activo'),
(152,'Sensor de gas MQ-135','Sensor',NULL,'activo'),
(151,'Sensor de gas MQ-2','Sensor',NULL,'activo'),
(145,'Sensor de humedad DHT11','Sensor',NULL,'activo'),
(146,'Sensor de humedad DHT22','Sensor',NULL,'activo'),
(149,'Sensor de luz LDR','Sensor',NULL,'activo'),
(148,'Sensor de movimiento PIR HC-SR501','Sensor',NULL,'activo'),
(156,'Sensor de presion BMP280','Sensor',NULL,'activo'),
(150,'Sensor de sonido KY-038','Sensor',NULL,'activo'),
(144,'Sensor de temperatura DS18B20','Sensor',NULL,'activo'),
(143,'Sensor de temperatura LM35','Sensor',NULL,'activo'),
(154,'Sensor infrarrojo TCRT5000','Sensor',NULL,'activo'),
(147,'Sensor ultrasonico HC-SR04','Sensor',NULL,'activo'),
(192,'Termistor NTC 10 KOhms','Protección',NULL,'activo'),
(193,'Termistor PTC','Protección',NULL,'activo'),
(108,'Transistor Darlington TIP120','Transistor',NULL,'activo'),
(100,'Transistor NPN 2N2222','Transistor',NULL,'activo'),
(101,'Transistor NPN 2N3904','Transistor',NULL,'activo'),
(98,'Transistor NPN BC547','Transistor',NULL,'activo'),
(99,'Transistor NPN BC548','Transistor',NULL,'activo'),
(102,'Transistor NPN TIP31C','Transistor',NULL,'activo'),
(103,'Transistor NPN TIP41C','Transistor',NULL,'activo'),
(105,'Transistor PNP 2N2907','Transistor',NULL,'activo'),
(106,'Transistor PNP 2N3906','Transistor',NULL,'activo'),
(104,'Transistor PNP BC557','Transistor',NULL,'activo'),
(107,'Transistor PNP TIP32C','Transistor',NULL,'activo'),
(42,'Trimmer 10 KOhms','Potenciómetro',NULL,'activo'),
(43,'Trimmer 100 KOhms','Potenciómetro',NULL,'activo'),
(125,'ULN2003 driver de motores','Motor',NULL,'activo'),
(194,'Varistor 14D471K','Protección',NULL,'activo');

INSERT INTO empleados (id_empleado, nombre, puesto, nfc_id, contrasena) VALUES (6,'Jimmy','CEO','698A00F4','pbkdf2_sha256$260000$c3b8d740ea025791ac4211f30c168a3b$fc7fe9dc5f8b317127f51564aecd2a90ed1715810c5d1a60097e49d0cb99614d');

INSERT INTO inventario
  (id_inventario, id_componente, cantidad, ubicacion, precio, stock_minimo)
VALUES
(7,15,120,'A1',0.50,10),
(8,18,199,'A1',0.50,10),
(9,24,180,'A2',0.50,10),
(10,27,100,'A2',0.60,10),
(11,30,80,'A2',0.60,10),
(12,37,25,'A3',8.50,10),
(13,51,149,'B1',1.00,10),
(14,53,79,'B1',1.50,10),
(15,56,46,'B2',1.50,10),
(16,59,67,'B2',2.50,10),
(17,62,30,'B2',8.00,10),
(18,72,100,'C1',1.00,10),
(19,74,80,'C1',0.80,10),
(20,75,39,'C1',2.50,10),
(21,78,48,'C2',1.50,10),
(22,85,98,'D1',0.80,10),
(23,87,78,'D1',0.80,10),
(24,89,70,'D1',1.20,10),
(25,91,60,'D1',1.20,10),
(26,92,29,'D2',3.50,10),
(27,100,38,'E1',3.00,10),
(28,98,49,'E1',2.50,10),
(29,104,29,'E1',2.50,10),
(30,108,15,'E2',12.00,10),
(31,109,19,'E2',18.00,10),
(32,110,14,'E2',20.00,10),
(33,113,8,'E2',22.00,10),
(34,116,30,'F1',5.00,10),
(35,118,25,'F1',6.00,10),
(36,119,20,'F1',8.00,10),
(37,122,15,'F1',12.00,10),
(38,123,12,'F2',25.00,10),
(39,124,10,'F2',35.00,10),
(40,126,40,'F2',3.50,10),
(41,133,29,'G1',5.00,10),
(42,137,19,'G1',8.00,10),
(43,139,22,'G1',4.50,10),
(44,141,13,'G2',25.00,10),
(45,143,10,'H1',20.00,10),
(46,144,12,'H1',25.00,10),
(47,145,10,'H1',35.00,10),
(48,147,15,'H2',30.00,10),
(49,148,10,'H2',25.00,10),
(50,151,8,'H2',40.00,10),
(51,157,50,'I1',2.00,10),
(52,159,24,'I1',5.00,10),
(53,162,18,'I1',6.00,10),
(54,166,28,'J1',8.00,10),
(55,168,18,'J1',5.00,10),
(56,174,12,'J2',12.00,10),
(57,178,19,'K1',5.00,10),
(58,180,17,'K1',8.00,10),
(59,182,14,'K2',15.00,10),
(60,186,39,'K2',2.50,10),
(61,196,8,'K3',25.00,10);

INSERT INTO pedidos
  (id_pedido, id_empleado, fecha_hora, estado, comentarios)
VALUES
(1,6,'2026-11-17 04:31:07','retirado',''),(2,6,'2026-11-17 04:59:57','retirado',''),(3,6,'2026-11-17 05:05:51','retirado',''),(4,6,'2026-11-17 05:12:28','retirado',''),(5,6,'2026-11-17 05:12:48','retirado',''),(6,6,'2026-11-17 14:14:20','retirado',''),(7,6,'2026-11-17 22:03:47','retirado',''),(8,6,'2026-11-17 22:06:01','retirado',''),(9,6,'2026-11-17 22:06:54','retirado',''),(10,6,'2026-11-17 22:09:38','retirado',''),(11,6,'2026-11-18 03:20:25','retirado',''),(12,6,'2026-11-19 23:46:38','retirado','');

INSERT INTO historial_pedidos
  (id_historial, id_componente, id_empleado, cantidad, fecha_hora, recibido, id_pedido)
VALUES
(11,53,6,1,'2026-11-17 04:31:07',1,1),(12,51,6,3,'2026-11-17 04:31:07',1,1),(13,56,6,1,'2026-11-17 04:31:07',1,1),(14,180,6,1,'2026-11-17 04:59:57',1,2),(15,53,6,2,'2026-11-17 04:59:57',1,2),(16,141,6,2,'2026-11-17 04:59:57',1,2),(17,168,6,4,'2026-11-17 05:05:51',1,3),(18,168,6,3,'2026-11-17 05:12:28',1,4),(19,180,6,1,'2026-11-17 05:12:48',1,5),(20,14,6,1,'2026-11-17 14:14:20',1,6),(21,180,6,1,'2026-11-17 14:14:20',1,6),(22,59,6,2,'2026-11-17 14:14:20',1,6),(23,180,6,1,'2026-11-17 22:03:47',1,7),(24,56,6,1,'2026-11-17 22:03:47',1,7),(25,174,6,3,'2026-11-17 22:03:47',1,7),(26,168,6,3,'2026-11-17 22:06:01',1,8),(27,53,6,1,'2026-11-17 22:06:01',1,8),(28,56,6,2,'2026-11-17 22:06:01',1,8),(29,59,6,1,'2026-11-17 22:06:01',1,8),(30,141,6,2,'2026-11-17 22:06:01',1,8),(31,178,6,1,'2026-11-17 22:06:01',1,8),(32,75,6,1,'2026-11-17 22:06:01',1,8),(33,78,6,2,'2026-11-17 22:06:01',1,8),(34,166,6,2,'2026-11-17 22:06:01',1,8),(35,159,6,1,'2026-11-17 22:06:01',1,8),(36,186,6,1,'2026-11-17 22:06:01',1,8),(37,92,6,1,'2026-11-17 22:06:01',1,8),(38,85,6,2,'2026-11-17 22:06:01',1,8),(39,87,6,2,'2026-11-17 22:06:01',1,8),(40,137,6,1,'2026-11-17 22:06:01',1,8),(41,182,6,1,'2026-11-17 22:06:01',1,8),(42,18,6,1,'2026-11-17 22:06:01',1,8),(43,139,6,3,'2026-11-17 22:06:01',1,8),(44,104,6,1,'2026-11-17 22:06:01',1,8),(45,98,6,1,'2026-11-17 22:06:01',1,8),(46,100,6,2,'2026-11-17 22:06:01',1,8),(47,113,6,2,'2026-11-17 22:06:54',1,9),(48,196,6,2,'2026-11-17 22:06:54',1,9),(49,109,6,1,'2026-11-17 22:06:54',1,9),(50,110,6,1,'2026-11-17 22:06:54',1,9),(51,133,6,1,'2026-11-17 22:06:54',1,9),(52,162,6,2,'2026-11-17 22:09:38',1,10),(53,168,6,1,'2026-11-18 03:20:25',1,11),(54,51,6,1,'2026-11-19 23:46:38',1,12),(55,56,6,1,'2026-11-19 23:46:38',1,12);
