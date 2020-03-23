SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET AUTOCOMMIT = 0;
START TRANSACTION;
SET time_zone = "+00:00";

--
-- Database: `Customer`
--
CREATE DATABASE IF NOT EXISTS `customer` DEFAULT CHARACTER SET utf8 COLLATE utf8_general_ci;
USE `customer`;

-- --------------------------------------------------------

--
-- Table structure for table `reward`
--

DROP TABLE IF EXISTS `user`;
CREATE TABLE IF NOT EXISTS `user` (
  `user_id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(32) NOT NULL,
  `point` INT NOT NULL,
  `exp` INT NOT NULL,
  `telehandle` VARCHAR(32) NOT NULL,
  `tele_id` INT,
  `email` VARCHAR(64),
  PRIMARY KEY (`user_id`)
);

--
-- Dumping data for table `user`
--

INSERT INTO `user` VALUES
(NULL,'Apple TAN',1000,2000,'apple_tan',NULL,NULL), 
(NULL,'Glen See',2000,4000,"glen_see",284805668,'glen.see.2018@sis.smu.edu.sg');

-- --------------------------------------------------------