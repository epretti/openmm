import unittest
from validateConstraints import *
from openmm.app import *
from openmm import *
from openmm.unit import *
import openmm.app.element as elem
import openmm.app.forcefield as forcefield
import math
import shutil
import tempfile
import textwrap
try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO
import os
import warnings

class TestForceField(unittest.TestCase):
    """Test the ForceField.createSystem() method."""

    def setUp(self):
        """Set up the tests by loading the input pdb files and force field
        xml files.

        """
        # alanine dipeptide with explicit water
        self.pdb1 = PDBFile('systems/alanine-dipeptide-explicit.pdb')
        self.forcefield1 = ForceField('amber99sb.xml', 'tip3p.xml')
        self.topology1 = self.pdb1.topology
        self.topology1.setUnitCellDimensions(Vec3(2, 2, 2))

        # alanine dipeptide with implicit water
        self.pdb2 = PDBFile('systems/alanine-dipeptide-implicit.pdb')
        self.forcefield2 = ForceField('amber99sb.xml', 'amber99_obc.xml')


    def test_NonbondedMethod(self):
        """Test all six options for the nonbondedMethod parameter."""

        methodMap = {NoCutoff:NonbondedForce.NoCutoff,
                     CutoffNonPeriodic:NonbondedForce.CutoffNonPeriodic,
                     CutoffPeriodic:NonbondedForce.CutoffPeriodic,
                     Ewald:NonbondedForce.Ewald,
                     PME:NonbondedForce.PME,
                     LJPME:NonbondedForce.LJPME}
        for method in methodMap:
            system = self.forcefield1.createSystem(self.pdb1.topology,
                                                  nonbondedMethod=method)
            forces = system.getForces()
            self.assertTrue(any(isinstance(f, NonbondedForce) and
                                f.getNonbondedMethod()==methodMap[method]
                                for f in forces))

    def test_DispersionCorrection(self):
        """Test to make sure that the dispersion/long-range correction is set properly."""
        top = Topology()
        chain = top.addChain()

        for lrc in (True, False):
            xml = textwrap.dedent(
                """
                <ForceField>
                 <LennardJonesForce lj14scale="0.3" useDispersionCorrection="{lrc}">
                  <Atom type="A" sigma="1" epsilon="0.1"/>
                  <Atom type="B" sigma="2" epsilon="0.2"/>
                  <NBFixPair type1="A" type2="B" sigma="2.5" epsilon="1.1"/>
                 </LennardJonesForce>
                 <NonbondedForce coulomb14scale="0.833333" lj14scale="0.5" useDispersionCorrection="{lrc2}">
                  <Atom type="A" sigma="0.315" epsilon="0.635"/>
                 </NonbondedForce>
                </ForceField>
                """
            )
            ff = ForceField(StringIO(xml.format(lrc=lrc, lrc2=lrc)))
            system = ff.createSystem(top)
            checked_nonbonded = False
            checked_custom = False
            for force in system.getForces():
                if isinstance(force, NonbondedForce):
                    self.assertEqual(force.getUseDispersionCorrection(), lrc)
                    checked_nonbonded = True
                elif isinstance(force, CustomNonbondedForce):
                    self.assertEqual(force.getUseLongRangeCorrection(), lrc)
                    checked_custom = True
            self.assertTrue(checked_nonbonded and checked_custom)

            # check that the keyword argument overwrites xml input
            lrc_kwarg = not lrc
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                system2 = ff.createSystem(top, useDispersionCorrection=lrc_kwarg)
                self.assertTrue(len(w) == 2)
                assert "conflict" in str(w[-1].message).lower()
            checked_nonbonded = False
            checked_custom = False
            for force in system2.getForces():
                if isinstance(force, NonbondedForce):
                    self.assertEqual(force.getUseDispersionCorrection(), lrc_kwarg)
                    checked_nonbonded = True
                elif isinstance(force, CustomNonbondedForce):
                    self.assertEqual(force.getUseLongRangeCorrection(), lrc_kwarg)
                    checked_custom = True
            self.assertTrue(checked_nonbonded and checked_custom)

            # check that no warning is generated when useDispersionCorrection is not in the xml file
            xml = textwrap.dedent(
                """
                <ForceField>
                 <LennardJonesForce lj14scale="0.3">
                  <Atom type="A" sigma="1" epsilon="0.1"/>
                  <Atom type="B" sigma="2" epsilon="0.2"/>
                  <NBFixPair type1="A" type2="B" sigma="2.5" epsilon="1.1"/>
                 </LennardJonesForce>
                 <NonbondedForce coulomb14scale="0.833333" lj14scale="0.5">
                  <Atom type="A" sigma="0.315" epsilon="0.635"/>
                 </NonbondedForce>
                </ForceField>
                """
            )
            ff = ForceField(StringIO(xml))
            system = ff.createSystem(top)
            for lrc_kwarg in [True, False]:
                with warnings.catch_warnings():
                    warnings.simplefilter("error")
                    system2 = ff.createSystem(top, useDispersionCorrection=lrc_kwarg)

    def test_Cutoff(self):
        """Test to make sure the nonbondedCutoff parameter is passed correctly."""

        for method in [CutoffNonPeriodic, CutoffPeriodic, Ewald, PME, LJPME]:
            system = self.forcefield1.createSystem(self.pdb1.topology,
                                                   nonbondedMethod=method,
                                                   nonbondedCutoff=2*nanometer,
                                                   constraints=HBonds)
            cutoff_distance = 0.0*nanometer
            cutoff_check = 2.0*nanometer
            for force in system.getForces():
                if isinstance(force, NonbondedForce):
                    cutoff_distance = force.getCutoffDistance()
            self.assertEqual(cutoff_distance, cutoff_check)

    def test_SwitchingDistance(self):
        """Test that the switchDistance parameter is processed correctly."""

        for switchDistance in [None, 0.9*nanometers]:
            system = self.forcefield1.createSystem(self.pdb1.topology,
                                                   nonbondedMethod=PME,
                                                   switchDistance=switchDistance)
            for force in system.getForces():
                if isinstance(force, NonbondedForce):
                    if switchDistance is None:
                        self.assertFalse(force.getUseSwitchingFunction())
                    else:
                        self.assertTrue(force.getUseSwitchingFunction())
                        self.assertEqual(switchDistance, force.getSwitchingDistance())

    def test_RemoveCMMotion(self):
        """Test both options (True and False) for the removeCMMotion parameter."""
        for b in [True, False]:
            system = self.forcefield1.createSystem(self.pdb1.topology,removeCMMotion=b)
            forces = system.getForces()
            self.assertEqual(any(isinstance(f, CMMotionRemover) for f in forces), b)

    def test_RigidWaterAndConstraints(self):
        """Test all eight options for the constraints and rigidWater parameters."""

        topology = self.pdb1.topology
        for constraints_value in [None, HBonds, AllBonds, HAngles]:
            for rigidWater_value in [True, False, None]:
                system = self.forcefield1.createSystem(topology,
                                                       constraints=constraints_value,
                                                       rigidWater=rigidWater_value)
                validateConstraints(self, topology, system,
                                    constraints_value, rigidWater_value != False)

    def test_flexibleConstraints(self):
        """ Test the flexibleConstraints keyword """
        topology = self.pdb1.topology
        system1 = self.forcefield1.createSystem(topology, constraints=HAngles,
                                                rigidWater=True)
        system2 = self.forcefield1.createSystem(topology, constraints=HAngles,
                                                rigidWater=True, flexibleConstraints=True)
        system3 = self.forcefield1.createSystem(topology, constraints=None, rigidWater=False)
        validateConstraints(self, topology, system1, HAngles, True)
        # validateConstraints fails for system2 since by definition atom pairs can be in both bond
        # and constraint lists. So just check that the number of constraints is the same for both
        # system1 and system2
        self.assertEqual(system1.getNumConstraints(), system2.getNumConstraints())
        for force in system1.getForces():
            if isinstance(force, HarmonicBondForce):
                bf1 = force
            elif isinstance(force, HarmonicAngleForce):
                af1 = force
        for force in system2.getForces():
            if isinstance(force, HarmonicBondForce):
                bf2 = force
            elif isinstance(force, HarmonicAngleForce):
                af2 = force
        for force in system3.getForces():
            if isinstance(force, HarmonicAngleForce):
                af3 = force
        # Make sure we picked up extra bond terms with flexibleConstraints
        self.assertGreater(bf2.getNumBonds(), bf1.getNumBonds())
        # Make sure flexibleConstraints yields just as many angles as no constraints
        self.assertEqual(af2.getNumAngles(), af3.getNumAngles())

    def test_ImplicitSolvent(self):
        """Test the four types of implicit solvents using the implicitSolvent
        parameter.

        """

        topology = self.pdb2.topology
        system = self.forcefield2.createSystem(topology)
        forces = system.getForces()
        self.assertTrue(any(isinstance(f, GBSAOBCForce) for f in forces))

    def test_ImplicitSolventParameters(self):
        """Test that solventDielectric and soluteDielectric are passed correctly
        for the different types of implicit solvent.

        """

        topology = self.pdb2.topology
        system = self.forcefield2.createSystem(topology, solventDielectric=50.0,
                                               soluteDielectric=0.9)
        found_matching_solvent_dielectric=False
        found_matching_solute_dielectric=False
        for force in system.getForces():
            if isinstance(force, GBSAOBCForce):
                if force.getSolventDielectric() == 50.0:
                    found_matching_solvent_dielectric = True
                if force.getSoluteDielectric() == 0.9:
                    found_matching_solute_dielectric = True
            if isinstance(force, NonbondedForce):
                self.assertEqual(force.getReactionFieldDielectric(), 1.0)
        self.assertTrue(found_matching_solvent_dielectric and
                        found_matching_solute_dielectric)

    def test_HydrogenMass(self):
        """Test that altering the mass of hydrogens works correctly."""

        topology = self.pdb1.topology
        hydrogenMass = 4*amu
        system1 = self.forcefield1.createSystem(topology)
        system2 = self.forcefield1.createSystem(topology, hydrogenMass=hydrogenMass)
        for atom in topology.atoms():
            if atom.element == elem.hydrogen:
                self.assertNotEqual(hydrogenMass, system1.getParticleMass(atom.index))
                if atom.residue.name == 'HOH':
                    self.assertEqual(system1.getParticleMass(atom.index), system2.getParticleMass(atom.index))
                else:
                    self.assertEqual(hydrogenMass, system2.getParticleMass(atom.index))
        totalMass1 = sum([system1.getParticleMass(i) for i in range(system1.getNumParticles())]).value_in_unit(amu)
        totalMass2 = sum([system2.getParticleMass(i) for i in range(system2.getNumParticles())]).value_in_unit(amu)
        self.assertAlmostEqual(totalMass1, totalMass2)

    def test_DrudeMass(self):
        """Test that setting the mass of Drude particles works correctly."""

        forcefield = ForceField('charmm_polar_2013.xml')
        pdb = PDBFile('systems/ala_ala_ala.pdb')
        modeller = Modeller(pdb.topology, pdb.positions)
        modeller.addExtraParticles(forcefield)
        system = forcefield.createSystem(modeller.topology, drudeMass=0)
        trueMass = [system.getParticleMass(i) for i in range(system.getNumParticles())]
        drudeMass = 0.3*amu
        system = forcefield.createSystem(modeller.topology, drudeMass=drudeMass)
        adjustedMass = [system.getParticleMass(i) for i in range(system.getNumParticles())]
        drudeForce = [f for f in system.getForces() if isinstance(f, DrudeForce)][0]
        drudeParticles = set()
        parentParticles = set()
        for i in range(drudeForce.getNumParticles()):
            params = drudeForce.getParticleParameters(i)
            drudeParticles.add(params[0])
            parentParticles.add(params[1])
        for i in range(system.getNumParticles()):
            if i in drudeParticles:
                self.assertEqual(0*amu, trueMass[i])
                self.assertEqual(drudeMass, adjustedMass[i])
            elif i in parentParticles:
                self.assertEqual(trueMass[i]-drudeMass, adjustedMass[i])
            else:
                self.assertEqual(trueMass[i], adjustedMass[i])

    def test_UnusedArgs(self):
        """Test that specifying an argument that is never used throws an exception."""
        topology = self.pdb1.topology
        # Using the default value should not raise an exception.
        self.forcefield1.createSystem(topology, drudeMass=0.4*amu)
        # Specifying a non-default value should.
        with self.assertRaises(ValueError):
            self.forcefield1.createSystem(topology, drudeMass=0.5*amu)
        # Specifying a nonexistant argument should raise an exception.
        with self.assertRaises(ValueError):
            self.forcefield1.createSystem(topology, nonbndedCutoff=1.0*nanometer)

    def test_Forces(self):
        """Compute forces and compare them to ones generated with a previous version of OpenMM to ensure they haven't changed."""

        pdb = PDBFile('systems/lysozyme-implicit.pdb')
        system = self.forcefield2.createSystem(pdb.topology)
        integrator = VerletIntegrator(0.001)
        context = Context(system, integrator)
        context.setPositions(pdb.positions)
        state1 = context.getState(getForces=True)
        with open('systems/lysozyme-implicit-forces.xml') as input:
            state2 = XmlSerializer.deserialize(input.read())
        numDifferences = 0
        for f1, f2, in zip(state1.getForces().value_in_unit(kilojoules_per_mole/nanometer), state2.getForces().value_in_unit(kilojoules_per_mole/nanometer)):
            diff = norm(f1-f2)
            if diff > 0.1 and diff/norm(f1) > 1e-3:
                numDifferences += 1
        self.assertTrue(numDifferences < system.getNumParticles()/20) # Tolerate occasional differences from numerical error

    def test_ImplicitSolventForces(self):
        """Compute forces for different implicit solvent types, and compare them to ones generated with AmberPrmtopFile."""

        solventType = ['hct', 'obc1', 'obc2', 'gbn', 'gbn2']
        nonbondedMethod = [NoCutoff, CutoffNonPeriodic, CutoffNonPeriodic, NoCutoff, NoCutoff]
        kappa = [0.0, 0.0, 1.698295227342757, 1.698295227342757, 0.0]
        file = [None, 'OBC1_NonPeriodic', 'OBC2_NonPeriodic_Salt', None, 'GBn2_NoCutoff']
        for i in range(len(file)):
            forcefield = ForceField('amber96.xml', f'implicit/{solventType[i]}.xml')
            system = forcefield.createSystem(self.pdb2.topology, nonbondedMethod=nonbondedMethod[i], implicitSolventKappa=kappa[i])
            integrator = VerletIntegrator(0.001)
            context = Context(system, integrator, Platform.getPlatform("Reference"))
            context.setPositions(self.pdb2.positions)
            state1 = context.getState(getForces=True)
            if file[i] is not None:
                with open('systems/alanine-dipeptide-implicit-forces/'+file[i]+'.xml') as infile:
                    state2 = XmlSerializer.deserialize(infile.read())
                for f1, f2, in zip(state1.getForces().value_in_unit(kilojoules_per_mole/nanometer), state2.getForces().value_in_unit(kilojoules_per_mole/nanometer)):
                    diff = norm(f1-f2)
                    self.assertTrue(diff < 0.1 or diff/norm(f1) < 1e-4)

    def test_ProgrammaticForceField(self):
        """Test building a ForceField programmatically."""

        # Build the ForceField for TIP3P programmatically.
        ff = ForceField()
        ff.registerAtomType({'name':'tip3p-O', 'class':'OW', 'mass':15.99943*daltons, 'element':elem.oxygen})
        ff.registerAtomType({'name':'tip3p-H', 'class':'HW', 'mass':1.007947*daltons, 'element':elem.hydrogen})
        residue = ForceField._TemplateData('HOH')
        residue.atoms.append(ForceField._TemplateAtomData('O', 'tip3p-O', elem.oxygen))
        residue.atoms.append(ForceField._TemplateAtomData('H1', 'tip3p-H', elem.hydrogen))
        residue.atoms.append(ForceField._TemplateAtomData('H2', 'tip3p-H', elem.hydrogen))
        residue.addBond(0, 1)
        residue.addBond(0, 2)
        ff.registerResidueTemplate(residue)
        bonds = forcefield.HarmonicBondGenerator(ff)
        bonds.registerBond({'class1':'OW', 'class2':'HW', 'length':0.09572*nanometers, 'k':462750.4*kilojoules_per_mole/nanometer})
        ff.registerGenerator(bonds)
        angles = forcefield.HarmonicAngleGenerator(ff)
        angles.registerAngle({'class1':'HW', 'class2':'OW', 'class3':'HW', 'angle':1.82421813418*radians, 'k':836.8*kilojoules_per_mole/radian})
        ff.registerGenerator(angles)
        nonbonded = forcefield.NonbondedGenerator(ff, 0.833333, 0.5, True)
        nonbonded.registerAtom({'type':'tip3p-O', 'charge':-0.834, 'sigma':0.31507524065751241*nanometers, 'epsilon':0.635968*kilojoules_per_mole})
        nonbonded.registerAtom({'type':'tip3p-H', 'charge':0.417, 'sigma':1*nanometers, 'epsilon':0*kilojoules_per_mole})
        ff.registerGenerator(nonbonded)

        # Build a water box.
        modeller = Modeller(Topology(), [])
        modeller.addSolvent(ff, boxSize=Vec3(3, 3, 3)*nanometers)

        # Create a system using the programmatic force field as well as one from an XML file.
        system1 = ff.createSystem(modeller.topology)
        ff2 = ForceField('tip3p.xml')
        system2 = ff2.createSystem(modeller.topology)
        self.assertEqual(XmlSerializer.serialize(system1), XmlSerializer.serialize(system2))

    def test_PeriodicBoxVectors(self):
        """Test setting the periodic box vectors."""

        vectors = (Vec3(5, 0, 0), Vec3(-1.5, 4.5, 0), Vec3(0.4, 0.8, 7.5))*nanometers
        self.pdb1.topology.setPeriodicBoxVectors(vectors)
        self.assertEqual(Vec3(5, 4.5, 7.5)*nanometers, self.pdb1.topology.getUnitCellDimensions())
        system = self.forcefield1.createSystem(self.pdb1.topology)
        for i in range(3):
            self.assertEqual(vectors[i], self.pdb1.topology.getPeriodicBoxVectors()[i])
            self.assertEqual(vectors[i], system.getDefaultPeriodicBoxVectors()[i])

    def test_duplicateAtomTypeAllowed(self):
        """Test that multiple registrations of the same atom type with identical definitions are allowed."""

        xml1 = """
<ForceField>
 <AtomTypes>
  <Type name="test-name" class="test" element="H" mass="1.007947"/>
 </AtomTypes>
</ForceField>"""

        xml2 = """
<ForceField>
 <AtomTypes>
  <Type name="test-name" class="test" element="H" mass="1.007947"/>
 </AtomTypes>
</ForceField>"""

        ff = ForceField(StringIO(xml1), StringIO(xml2))

        self.assertTrue("test-name" in ff._atomTypes)
        at = ff._atomTypes["test-name"]
        self.assertEqual(at.atomClass, "test")
        self.assertEqual(at.element, elem.hydrogen)
        self.assertEqual(at.mass, 1.007947)

    def test_duplicateAtomTypeAllowedNoElement(self):
        """Test that multiple registrations of the same atom type with identical definitions and without elements are allowed."""

        xml1 = """
<ForceField>
 <AtomTypes>
  <Type name="test-name" class="test" mass="0.0"/>
 </AtomTypes>
</ForceField>"""

        xml2 = """
<ForceField>
 <AtomTypes>
  <Type name="test-name" class="test" mass="0.0"/>
 </AtomTypes>
</ForceField>"""

        ff = ForceField(StringIO(xml1), StringIO(xml2))

        self.assertTrue("test-name" in ff._atomTypes)
        at = ff._atomTypes["test-name"]
        self.assertEqual(at.atomClass, "test")
        self.assertEqual(at.element, None)
        self.assertEqual(at.mass, 0.0)

    def test_duplicateAtomTypeForbiddenClass(self):
        """Test that multiple registrations of the same atom type with different classes are forbidden."""

        xml1 = """
<ForceField>
 <AtomTypes>
  <Type name="test-name" class="test-1" element="H" mass="1.007947"/>
 </AtomTypes>
</ForceField>"""

        xml2 = """
<ForceField>
 <AtomTypes>
  <Type name="test-name" class="test-2" element="H" mass="1.007947"/>
 </AtomTypes>
</ForceField>"""

        with self.assertRaises(ValueError):
            ff = ForceField(StringIO(xml1), StringIO(xml2))

    def test_duplicateAtomTypeForbiddenElement(self):
        """Test that multiple registrations of the same atom type with different elements are forbidden."""

        xml1 = """
<ForceField>
 <AtomTypes>
  <Type name="test-name" class="test" element="H" mass="1.007947"/>
 </AtomTypes>
</ForceField>"""

        xml2 = """
<ForceField>
 <AtomTypes>
  <Type name="test-name" class="test" element="C" mass="1.007947"/>
 </AtomTypes>
</ForceField>"""

        with self.assertRaises(ValueError):
            ff = ForceField(StringIO(xml1), StringIO(xml2))

    def test_duplicateAtomTypeForbiddenElementAdded(self):
        """Test that multiple registrations of the same atom type, the first without and the second with an element, are forbidden."""

        xml1 = """
<ForceField>
 <AtomTypes>
  <Type name="test-name" class="test" mass="1.007947"/>
 </AtomTypes>
</ForceField>"""

        xml2 = """
<ForceField>
 <AtomTypes>
  <Type name="test-name" class="test" element="H" mass="1.007947"/>
 </AtomTypes>
</ForceField>"""

        with self.assertRaises(ValueError):
            ff = ForceField(StringIO(xml1), StringIO(xml2))

    def test_duplicateAtomTypeForbiddenElementRemoved(self):
        """Test that multiple registrations of the same atom type, the first with and the second without an element, are forbidden."""

        xml1 = """
<ForceField>
 <AtomTypes>
  <Type name="test-name" class="test" element="H" mass="1.007947"/>
 </AtomTypes>
</ForceField>"""

        xml2 = """
<ForceField>
 <AtomTypes>
  <Type name="test-name" class="test" mass="1.007947"/>
 </AtomTypes>
</ForceField>"""

        with self.assertRaises(ValueError):
            ff = ForceField(StringIO(xml1), StringIO(xml2))

    def test_duplicateAtomTypeForbiddenMass(self):
        """Test that multiple registrations of the same atom type with different masses are forbidden."""

        xml1 = """
<ForceField>
 <AtomTypes>
  <Type name="test-name" class="test" element="H" mass="1.007947"/>
 </AtomTypes>
</ForceField>"""

        xml2 = """
<ForceField>
 <AtomTypes>
  <Type name="test-name" class="test" element="H" mass="12.01078"/>
 </AtomTypes>
</ForceField>"""

        with self.assertRaises(ValueError):
            ff = ForceField(StringIO(xml1), StringIO(xml2))

    def test_ResidueAttributes(self):
        """Test a ForceField that gets per-particle parameters from residue attributes."""

        xml = """
<ForceField>
 <AtomTypes>
  <Type name="tip3p-O" class="OW" element="O" mass="15.99943"/>
  <Type name="tip3p-H" class="HW" element="H" mass="1.007947"/>
 </AtomTypes>
 <Residues>
  <Residue name="HOH">
   <Atom name="O" type="tip3p-O" charge="-0.834"/>
   <Atom name="H1" type="tip3p-H" charge="0.417"/>
   <Atom name="H2" type="tip3p-H" charge="0.417"/>
   <Bond from="0" to="1"/>
   <Bond from="0" to="2"/>
  </Residue>
 </Residues>
 <NonbondedForce coulomb14scale="0.833333" lj14scale="0.5">
  <UseAttributeFromResidue name="charge"/>
  <Atom type="tip3p-O" sigma="0.315" epsilon="0.635"/>
  <Atom type="tip3p-H" sigma="1" epsilon="0"/>
 </NonbondedForce>
</ForceField>"""
        ff = ForceField(StringIO(xml))

        # Build a water box.
        modeller = Modeller(Topology(), [])
        modeller.addSolvent(ff, boxSize=Vec3(3, 3, 3)*nanometers)

        # Create a system and make sure all nonbonded parameters are correct.
        system = ff.createSystem(modeller.topology)
        nonbonded = [f for f in system.getForces() if isinstance(f, NonbondedForce)][0]
        atoms = list(modeller.topology.atoms())
        for i in range(len(atoms)):
            params = nonbonded.getParticleParameters(i)
            if atoms[i].element == elem.oxygen:
                self.assertEqual(params[0], -0.834*elementary_charge)
                self.assertEqual(params[1], 0.315*nanometers)
                self.assertEqual(params[2], 0.635*kilojoule_per_mole)
            else:
                self.assertEqual(params[0], 0.417*elementary_charge)
                self.assertEqual(params[1], 1.0*nanometers)
                self.assertEqual(params[2], 0.0*kilojoule_per_mole)

    def test_residueMatcher(self):
        """Test using a custom template matcher to select templates."""
        xml = """
<ForceField>
 <AtomTypes>
  <Type name="tip3p-O" class="OW" element="O" mass="15.99943"/>
  <Type name="tip3p-H" class="HW" element="H" mass="1.007947"/>
 </AtomTypes>
 <Residues>
  <Residue name="HOH">
   <Atom name="O" type="tip3p-O" charge="-0.834"/>
   <Atom name="H1" type="tip3p-H" charge="0.417"/>
   <Atom name="H2" type="tip3p-H" charge="0.417"/>
   <Bond from="0" to="1"/>
   <Bond from="0" to="2"/>
  </Residue>
  <Residue name="HOH2">
   <Atom name="O" type="tip3p-O" charge="0.834"/>
   <Atom name="H1" type="tip3p-H" charge="-0.417"/>
   <Atom name="H2" type="tip3p-H" charge="-0.417"/>
   <Bond from="0" to="1"/>
   <Bond from="0" to="2"/>
  </Residue>
 </Residues>
 <NonbondedForce coulomb14scale="0.833333" lj14scale="0.5">
  <UseAttributeFromResidue name="charge"/>
  <Atom type="tip3p-O" sigma="0.315" epsilon="0.635"/>
  <Atom type="tip3p-H" sigma="1" epsilon="0"/>
 </NonbondedForce>
</ForceField>"""
        ff = ForceField(StringIO(xml))

        # Load a water box.
        prmtop = AmberPrmtopFile('systems/water-box-216.prmtop')
        top = prmtop.topology
        
        # Building a System should fail, because two templates match each residue.
        self.assertRaises(Exception, lambda: ff.createSystem(top))
        
        # Register a template matcher that selects a particular one.
        def matcher(ff, res, bondedToAtom, ignoreExternalBonds, ignoreExtraParticles):
            return ff._templates['HOH2']
        ff.registerTemplateMatcher(matcher)
        
        # It should now succeed in building a System.
        system = ff.createSystem(top)
        
        # Make sure it used the correct parameters.
        nb = [f for f in system.getForces() if isinstance(f, NonbondedForce)][0]
        for atom in top.atoms():
            charge, sigma, epsilon = nb.getParticleParameters(atom.index)
            if atom.name == 'O':
                self.assertEqual(0.834*elementary_charge, charge)
            else:
                self.assertEqual(-0.417*elementary_charge, charge)

    def test_residueTemplateGenerator(self):
        """Test the ability to add residue template generators to parameterize unmatched residues."""
        def simpleTemplateGenerator(forcefield, residue):
            """\
            Simple residue template generator.
            This implementation uses the programmatic API to define residue templates.

            NOTE: We presume we have already loaded the force definitions into ForceField.
            """
            # Generate a unique prefix name for generating parameters.
            from uuid import uuid4
            template_name = uuid4()
            # Create residue template.
            from openmm.app.forcefield import _createResidueTemplate
            template = _createResidueTemplate(residue) # use helper function
            template.name = template_name # replace template name
            for (template_atom, residue_atom) in zip(template.atoms, residue.atoms()):
                template_atom.type = 'XXX' # replace atom type
            # Register the template.
            forcefield.registerResidueTemplate(template)

            # Signal that we have successfully parameterized the residue.
            return True

        # Define forcefield parameters used by simpleTemplateGenerator.
        # NOTE: This parameter definition file will currently only work for residues that either have
        # no external bonds or external bonds to other residues parameterized by the simpleTemplateGenerator.
        simple_ffxml_contents = """
<ForceField>
 <AtomTypes>
  <Type name="XXX" class="XXX" element="C" mass="12.0"/>
 </AtomTypes>
 <HarmonicBondForce>
  <Bond type1="XXX" type2="XXX" length="0.1409" k="392459.2"/>
 </HarmonicBondForce>
 <HarmonicAngleForce>
  <Angle type1="XXX" type2="XXX" type3="XXX" angle="2.09439510239" k="527.184"/>
 </HarmonicAngleForce>
 <NonbondedForce coulomb14scale="0.833333" lj14scale="0.5">
  <Atom type="XXX" charge="0.000" sigma="0.315" epsilon="0.635"/>
 </NonbondedForce>
</ForceField>"""

        #
        # Test where we generate parameters for only a ligand.
        #

        # Load the PDB file.
        pdb = PDBFile(os.path.join('systems', 'T4-lysozyme-L99A-p-xylene-implicit.pdb'))
        # Create a ForceField object.
        forcefield = ForceField('amber99sb.xml', 'tip3p.xml', StringIO(simple_ffxml_contents))
        # Add the residue template generator.
        forcefield.registerTemplateGenerator(simpleTemplateGenerator)
        # Parameterize system.
        system = forcefield.createSystem(pdb.topology, nonbondedMethod=NoCutoff)
        # TODO: Test energies are finite?

        #
        # Test for a few systems where we generate all parameters.
        #

        tests = [
            { 'pdb_filename' : 'alanine-dipeptide-implicit.pdb', 'nonbondedMethod' : NoCutoff },
            { 'pdb_filename' : 'lysozyme-implicit.pdb', 'nonbondedMethod' : NoCutoff },
            { 'pdb_filename' : 'alanine-dipeptide-explicit.pdb', 'nonbondedMethod' : CutoffPeriodic },
            ]

        # Test all systems with separate ForceField objects.
        for test in tests:
            # Load the PDB file.
            pdb = PDBFile(os.path.join('systems', test['pdb_filename']))
            # Create a ForceField object.
            forcefield = ForceField(StringIO(simple_ffxml_contents))
            # Add the residue template generator.
            forcefield.registerTemplateGenerator(simpleTemplateGenerator)
            # Parameterize system.
            system = forcefield.createSystem(pdb.topology, nonbondedMethod=test['nonbondedMethod'])
            # TODO: Test energies are finite?

        # Now test all systems with a single ForceField object.
        # Create a ForceField object.
        forcefield = ForceField(StringIO(simple_ffxml_contents))
        # Add the residue template generator.
        forcefield.registerTemplateGenerator(simpleTemplateGenerator)
        for test in tests:
            # Load the PDB file.
            pdb = PDBFile(os.path.join('systems', test['pdb_filename']))
            # Parameterize system.
            system = forcefield.createSystem(pdb.topology, nonbondedMethod=test['nonbondedMethod'])
            # TODO: Test energies are finite?

    def test_getUnmatchedResidues(self):
        """Test retrieval of list of residues for which no templates are available."""

        # Load the PDB file.
        pdb = PDBFile(os.path.join('systems', 'T4-lysozyme-L99A-p-xylene-implicit.pdb'))
        # Create a ForceField object.
        forcefield = ForceField('amber99sb.xml', 'tip3p.xml')
        # Get list of unmatched residues.
        unmatched_residues = forcefield.getUnmatchedResidues(pdb.topology)
        # Check results.
        self.assertEqual(len(unmatched_residues), 1)
        self.assertEqual(unmatched_residues[0].name, 'TMP')
        self.assertEqual(unmatched_residues[0].id, '163')

        # Load the PDB file.
        pdb = PDBFile(os.path.join('systems', 'ala_ala_ala.pdb'))
        # Create a ForceField object.
        forcefield = ForceField('tip3p.xml')
        # Get list of unmatched residues.
        unmatched_residues = forcefield.getUnmatchedResidues(pdb.topology)
        # Check results.
        self.assertEqual(len(unmatched_residues), 3)
        self.assertEqual(unmatched_residues[0].name, 'ALA')
        self.assertEqual(unmatched_residues[0].chain.id, 'X')
        self.assertEqual(unmatched_residues[0].id, '1')

    def test_generateTemplatesForUnmatchedResidues(self):
        """Test generation of blank forcefield residue templates for unmatched residues."""
        #
        # Test where we generate parameters for only a ligand.
        #

        # Load the PDB file.
        pdb = PDBFile(os.path.join('systems', 'nacl-water.pdb'))
        # Create a ForceField object.
        forcefield = ForceField('tip3p.xml')
        # Get list of unmatched residues.
        unmatched_residues = forcefield.getUnmatchedResidues(pdb.topology)
        [templates, residues] = forcefield.generateTemplatesForUnmatchedResidues(pdb.topology)
        # Check results.
        self.assertEqual(len(unmatched_residues), 24)
        self.assertEqual(len(residues), 2)
        self.assertEqual(len(templates), 2)
        unique_names = set([ residue.name for residue in residues ])
        self.assertTrue('HOH' not in unique_names)
        self.assertTrue('NA' in unique_names)
        self.assertTrue('CL' in unique_names)
        template_names = set([ template.name for template in templates ])
        self.assertTrue('HOH' not in template_names)
        self.assertTrue('NA' in template_names)
        self.assertTrue('CL' in template_names)

        # Define forcefield parameters using returned templates.
        # NOTE: This parameter definition file will currently only work for residues that either have
        # no external bonds or external bonds to other residues parameterized by the simpleTemplateGenerator.
        simple_ffxml_contents = """
<ForceField>
 <AtomTypes>
  <Type name="XXX" class="XXX" element="C" mass="12.0"/>
 </AtomTypes>
 <HarmonicBondForce>
  <Bond type1="XXX" type2="XXX" length="0.1409" k="392459.2"/>
 </HarmonicBondForce>
 <HarmonicAngleForce>
  <Angle type1="XXX" type2="XXX" type3="XXX" angle="2.09439510239" k="527.184"/>
 </HarmonicAngleForce>
 <NonbondedForce coulomb14scale="0.833333" lj14scale="0.5">
  <Atom type="XXX" charge="0.000" sigma="0.315" epsilon="0.635"/>
 </NonbondedForce>
</ForceField>"""

        #
        # Test the pre-geenration of missing residue template for a ligand.
        #

        # Load the PDB file.
        pdb = PDBFile(os.path.join('systems', 'T4-lysozyme-L99A-p-xylene-implicit.pdb'))
        # Create a ForceField object.
        forcefield = ForceField('amber99sb.xml', 'tip3p.xml', StringIO(simple_ffxml_contents))
        # Get list of unique unmatched residues.
        [templates, residues] = forcefield.generateTemplatesForUnmatchedResidues(pdb.topology)
        # Add residue templates to forcefield.
        for template in templates:
            # Replace atom types.
            for atom in template.atoms:
                atom.type = 'XXX'
            # Register the template.
            forcefield.registerResidueTemplate(template)
        # Parameterize system.
        system = forcefield.createSystem(pdb.topology, nonbondedMethod=NoCutoff)
        # TODO: Test energies are finite?

    def test_getMatchingTemplates(self):
        """Test retrieval of list of templates that match residues in a topology."""

        # Load the PDB file.
        pdb = PDBFile(os.path.join('systems', 'ala_ala_ala.pdb'))
        # Create a ForceField object.
        forcefield = ForceField('amber99sb.xml')
        # Get list of matching residue templates.
        templates = forcefield.getMatchingTemplates(pdb.topology)
        # Check results.
        residues = [ residue for residue in pdb.topology.residues() ]
        self.assertEqual(len(templates), len(residues))
        self.assertEqual(templates[0].name, 'NALA')
        self.assertEqual(templates[1].name, 'ALA')
        self.assertEqual(templates[2].name, 'CALA')

    def test_matchErrorMessages(self):
        """Test match error detection and diagnostics"""

        # Load a force field to test with and prepare some lines with which to build topologies from PDB files.
        forcefield = ForceField('amber14-all.xml', 'amber14/opc.xml')
        pdbLines = [
            'ATOM      0 CH3  ACE A   1       0       0       0                           C',
            'ATOM      1 HH31 ACE A   1       0       0       0                           H',
            'ATOM      2 HH32 ACE A   1       0       0       0                           H',
            'ATOM      3 HH33 ACE A   1       0       0       0                           H',
            'ATOM      4 C    ACE A   1       0       0       0                           C',
            'ATOM      5 O    ACE A   1       0       0       0                           O',
            'ATOM      6 N    GLY A   2       0       0       0                           N',
            'ATOM      7 H    GLY A   2       0       0       0                           H',
            'ATOM      8 CA   GLY A   2       0       0       0                           C',
            'ATOM      9 HA2  GLY A   2       0       0       0                           H',
            'ATOM     10 HA3  GLY A   2       0       0       0                           H',
            'ATOM     11 C    GLY A   2       0       0       0                           C',
            'ATOM     12 O    GLY A   2       0       0       0                           O',
            'ATOM     13 N    NME A   3       0       0       0                           N',
            'ATOM     14 H    NME A   3       0       0       0                           H',
            'ATOM     15 CH3  NME A   3       0       0       0                           C',
            'ATOM     16 HH31 NME A   3       0       0       0                           H',
            'ATOM     17 HH32 NME A   3       0       0       0                           H',
            'ATOM     18 HH33 NME A   3       0       0       0                           H',
        ]

        def makeSystem(lines):
            return forcefield.createSystem(PDBFile(StringIO("\n".join(lines))).topology)

        # This should succeed and not produce any match errors.
        self.assertEqual(makeSystem(pdbLines).getNumParticles(), 19)

        # Add an He atom and B atoms atom to GLY.
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*GLY.*The residue contains He atoms and B atoms, which are not supported by any template in the force field'):
            makeSystem(pdbLines[:9] + [
                'ATOM     19 X1   GLY A   2       0       0       0                          He',
                'ATOM     20 X2   GLY A   2       0       0       0                           B',
                'ATOM     21 X3   GLY A   2       0       0       0                           B',
            ] + pdbLines[9:])

        # Delete CA atom from GLY.
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*GLY.*The set of atoms is similar to GLY, but is missing 1 C atom'):
            makeSystem(pdbLines[:8] + pdbLines[9:])

        # Add an F atom to GLY.
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*GLY.*The set of atoms is similar to GLY, but has 1 F atom too many'):
            makeSystem(pdbLines[:9] + [
                'ATOM     19 X1   GLY A   2       0       0       0                           F',
            ] + pdbLines[9:])

        # Delete CA atom from GLY and add an F atom.
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*GLY.*The set of atoms is similar to GLY, but is missing 1 C atom and has 1 F atom too many'):
            makeSystem(pdbLines[:8] + [
                'ATOM     19 X1   GLY A   2       0       0       0                           F',
            ] + pdbLines[9:])

        # Add 1 F atom, 2 Cl atoms, and 1 Br atom to GLY.
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*GLY.*The set of atoms is similar to GLY, but has 1 F atom, 2 Cl atoms, and 1 Br atom too many'):
            makeSystem(pdbLines[:9] + [
                'ATOM     19 X1   GLY A   2       0       0       0                           F',
                'ATOM     20 X2   GLY A   2       0       0       0                          Cl',
                'ATOM     21 X3   GLY A   2       0       0       0                          Cl',
                'ATOM     22 X4   GLY A   2       0       0       0                          Br',
            ] + pdbLines[9:])

        # Add a virtual site to GLY.
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*GLY.*The set of heavy atoms matches GLY, but the residue has 1 extra site too many'):
            makeSystem(pdbLines[:9] + [
                'ATOM     19 X1   GLY A   2       0       0       0                          EP',
            ] + pdbLines[9:])

        # Delete HA3 atom from GLY.
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*GLY.*The set of heavy atoms matches GLY, but the residue is missing 1 H atom.*You may be able to add it with.*addHydrogens'):
            makeSystem(pdbLines[:10] + pdbLines[11:])

        # Delete HA2 and HA3 atoms from GLY.
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*GLY.*The set of heavy atoms matches GLY, but the residue is missing 2 H atoms.*You may be able to add them with.*addHydrogens'):
            makeSystem(pdbLines[:9] + pdbLines[11:])

        # Delete HA3 atom from GLY and add a virtual site.
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*GLY.*The set of heavy atoms matches GLY, but the residue is missing 1 H atom and has 1 extra site too many'):
            makeSystem(pdbLines[:10] + [
                'ATOM     19 X1   GLY A   2       0       0       0                          EP',
            ] + pdbLines[11:])

        # Rename HA3 atom to remove the CA-HA3 bond.
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*GLY.*The set of atoms matches GLY, but the residue is missing 1 H-C bond'):
            makeSystem(pdbLines[:10] + [
                'ATOM     10 X1   GLY A   2       0       0       0                           H',
            ] + pdbLines[11:])

        # Add an extra N-O bond.
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*GLY.*The set of atoms matches GLY, but the residue has 1 N-O bond too many'):
            makeSystem(pdbLines + [
                'CONECT    6   12'
            ])

        # Remove an external bond to NME by renaming its N atom.
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*GLY.*The atoms and bonds in the residue match GLY, but the set of externally bonded atoms is missing 1 C atom'):
            makeSystem(pdbLines[:13] + [
                'ATOM     13 X1   NME A   3       0       0       0                           N',
            ] + pdbLines[14:])

        # Add an extra external bond to NME.
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*GLY.*The atoms and bonds in the residue match GLY, but the set of externally bonded atoms has 1 O atom too many'):
            makeSystem(pdbLines + [
                'CONECT   12   15'
            ])

        # Delete ACE so that a capping group is missing from GLY.
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*GLY.*The atoms and bonds in the residue match GLY, but the set of externally bonded atoms is missing 1 N atom.*Is the chain missing a terminal capping group?'):
            makeSystem(pdbLines[6:])

        # Keep the atom/bond element fingerprint the same but change the connectivity.
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*GLY.*The atoms and bonds in the residue match GLY, but the connectivity is different'):
            # Rename O to break the C=O bond, but then reattach the O to the CA.
            makeSystem(pdbLines[:12] + [
                'ATOM     12 X1   GLY A   2       0       0       0                           O',
            ] + pdbLines[13:] + [
                'CONECT    8   12'
            ])

        # Make water with incorrect atom names so bonds will be missing.
        pdbLines = [
            'ATOM      0 X1   HOH A   1       0       0       0                           O',
            'ATOM      1 X2   HOH A   1       0       0       0                           H',
            'ATOM      2 X3   HOH A   1       0       0       0                           H',
        ]

        # Check for a special message when all bonds are missing.
        forcefield = ForceField('opc3.xml')
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*HOH.*The set of atoms matches HOH, but the residue has no bonds between its atoms'):
            makeSystem(pdbLines)

        # Add a site to a residue with a force field that doesn't support sites.
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*HOH.*The residue contains extra sites, which are not supported by any template in the force field'):
            makeSystem(pdbLines + [
                'ATOM      3 X4   HOH A   1       0       0       0                          EP',
            ])

        # Load a force field so that 1 site will be missing.
        forcefield = ForceField('opc.xml')
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*HOH.*The set of heavy atoms matches HOH, but the residue is missing 1 extra site.*You may be able to add it with.*addExtraParticles'):
            makeSystem(pdbLines)

        # Load a force field so that 2 sites will be missing.
        forcefield = ForceField('tip5p.xml')
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*HOH.*The set of heavy atoms matches HOH, but the residue is missing 2 extra sites.*You may be able to add them with.*addExtraParticles'):
            makeSystem(pdbLines)

        # Use an empty force field so that there are no templates.
        forcefield = ForceField()
        with self.assertRaisesRegex(ValueError, 'No template found for residue.*HOH.*The force field contains no residue templates'):
            makeSystem(pdbLines)

    def test_Wildcard(self):
        """Test that PeriodicTorsionForces using wildcard ('') for atom types / classes in the ffxml are correctly registered"""

        # Use wildcards in types
        xml = """
<ForceField>
 <AtomTypes>
  <Type name="C" class="C" element="C" mass="12.010000"/>
  <Type name="O" class="O" element="O" mass="16.000000"/>
 </AtomTypes>
 <PeriodicTorsionForce>
  <Proper type1="" type2="C" type3="C" type4="" periodicity1="2" phase1="3.141593" k1="15.167000"/>
  <Improper type1="C" type2="" type3="" type4="O" periodicity1="2" phase1="3.141593" k1="43.932000"/>
 </PeriodicTorsionForce>
</ForceField>"""

        ff = ForceField(StringIO(xml))

        self.assertEqual(len(ff._forces[0].proper), 1)
        self.assertEqual(len(ff._forces[0].improper), 1)

       # Use wildcards in classes
        xml = """
<ForceField>
 <AtomTypes>
  <Type name="C" class="C" element="C" mass="12.010000"/>
  <Type name="O" class="O" element="O" mass="16.000000"/>
 </AtomTypes>
 <PeriodicTorsionForce>
  <Proper class1="" class2="C" class3="C" class4="" periodicity1="2" phase1="3.141593" k1="15.167000"/>
  <Improper class1="C" class2="" class3="" class4="O" periodicity1="2" phase1="3.141593" k1="43.932000"/>
 </PeriodicTorsionForce>
</ForceField>"""

        ff = ForceField(StringIO(xml))

        self.assertEqual(len(ff._forces[0].proper), 1)
        self.assertEqual(len(ff._forces[0].improper), 1)

    def test_ScalingFactorCombining(self):
        """ Tests that FFs can be combined if their scaling factors are very close """
        forcefield = ForceField('amber99sb.xml', os.path.join('systems', 'test_amber_ff.xml'))
        # This would raise an exception if it didn't work

    def test_MultipleFilesandForceTags(self):
        """Test that the order of listing of multiple ffxmls does not matter.
           Tests that one generator per force type is created and that the ffxml
           defining atom types does not have to be listed first"""

        ffxml = """<ForceField>
 <Residues>
  <Residue name="ACE-Test">
   <Atom name="HH31" type="710"/>
   <Atom name="CH3" type="711"/>
   <Atom name="HH32" type="710"/>
   <Atom name="HH33" type="710"/>
   <Atom name="C" type="712"/>
   <Atom name="O" type="713"/>
   <Bond from="0" to="1"/>
   <Bond from="1" to="2"/>
   <Bond from="1" to="3"/>
   <Bond from="1" to="4"/>
   <Bond from="4" to="5"/>
   <ExternalBond from="4"/>
  </Residue>
 </Residues>
 <PeriodicTorsionForce>
  <Proper class1="C" class2="C" class3="C" class4="C" periodicity1="2" phase1="3.14159265359" k1="10.46"/>
  <Improper class1="C" class2="C" class3="C" class4="C" periodicity1="2" phase1="3.14159265359" k1="43.932"/>
 </PeriodicTorsionForce>
</ForceField>"""

        ff1 = ForceField(StringIO(ffxml), 'amber99sbildn.xml')
        ff2 = ForceField('amber99sbildn.xml', StringIO(ffxml))

        self.assertEqual(len(ff1._forces), 4)
        self.assertEqual(len(ff2._forces), 4)

        pertorsion1 = ff1._forces[0]
        pertorsion2 = ff2._forces[2]

        self.assertEqual(len(pertorsion1.proper), 110)
        self.assertEqual(len(pertorsion1.improper), 42)
        self.assertEqual(len(pertorsion2.proper), 110)
        self.assertEqual(len(pertorsion2.improper), 42)

    def test_ResidueTemplateUserChoice(self):
        """Test createSystem does not allow multiple matching templates, unless
           user has specified which template to use via residueTemplates arg"""
        ffxml = """<ForceField>
 <AtomTypes>
  <Type name="Fe2+" class="Fe2+" element="Fe" mass="55.85"/>
  <Type name="Fe3+" class="Fe3+" element="Fe" mass="55.85"/>
 </AtomTypes>
 <Residues>
  <Residue name="FE2">
   <Atom name="FE2" type="Fe2+" charge="2.0"/>
  </Residue>
  <Residue name="FE">
   <Atom name="FE" type="Fe3+" charge="3.0"/>
  </Residue>
 </Residues>
 <NonbondedForce coulomb14scale="0.833333333333" lj14scale="0.5">
  <UseAttributeFromResidue name="charge"/>
  <Atom type="Fe2+" sigma="0.227535532613" epsilon="0.0150312292"/>
  <Atom type="Fe3+" sigma="0.192790482606" epsilon="0.00046095128"/>
 </NonbondedForce>
</ForceField>"""

        pdb_string = "ATOM      1 FE    FE A   1      20.956  27.448 -29.067  1.00  0.00          Fe"
        ff = ForceField(StringIO(ffxml))
        pdb = PDBFile(StringIO(pdb_string))

        self.assertRaises(Exception, lambda: ff.createSystem(pdb.topology))
        sys = ff.createSystem(pdb.topology, residueTemplates={list(pdb.topology.residues())[0] : 'FE2'})
        # confirm charge
        self.assertEqual(sys.getForce(0).getParticleParameters(0)[0]._value, 2.0)
        sys = ff.createSystem(pdb.topology, residueTemplates={list(pdb.topology.residues())[0] : 'FE'})
        # confirm charge
        self.assertEqual(sys.getForce(0).getParticleParameters(0)[0]._value, 3.0)

    def test_ResidueOverriding(self):
        """Test residue overriding via override tag in the XML"""

        ffxml1 = """<ForceField>
 <AtomTypes>
  <Type name="Fe2+_tip3p_HFE" class="Fe2+_tip3p_HFE" element="Fe" mass="55.85"/>
 </AtomTypes>
 <Residues>
  <Residue name="FE2">
   <Atom name="FE2" type="Fe2+_tip3p_HFE" charge="2.0"/>
  </Residue>
 </Residues>
 <NonbondedForce coulomb14scale="0.833333333333" lj14scale="0.5">
  <UseAttributeFromResidue name="charge"/>
  <Atom type="Fe2+_tip3p_HFE" sigma="0.227535532613" epsilon="0.0150312292"/>
 </NonbondedForce>
</ForceField>"""

        ffxml2 = """<ForceField>
 <AtomTypes>
  <Type name="Fe2+_tip3p_standard" class="Fe2+_tip3p_standard" element="Fe" mass="55.85"/>
 </AtomTypes>
 <Residues>
  <Residue name="FE2">
   <Atom name="FE2" type="Fe2+_tip3p_standard" charge="2.0"/>
  </Residue>
 </Residues>
 <NonbondedForce coulomb14scale="0.833333333333" lj14scale="0.5">
  <UseAttributeFromResidue name="charge"/>
  <Atom type="Fe2+_tip3p_standard" sigma="0.241077193129" epsilon="0.03940482832"/>
 </NonbondedForce>
</ForceField>"""

        ffxml3 = """<ForceField>
 <AtomTypes>
  <Type name="Fe2+_tip3p_standard" class="Fe2+_tip3p_standard" element="Fe" mass="55.85"/>
 </AtomTypes>
 <Residues>
  <Residue name="FE2" override="1">
   <Atom name="FE2" type="Fe2+_tip3p_standard" charge="2.0"/>
  </Residue>
 </Residues>
 <NonbondedForce coulomb14scale="0.833333333333" lj14scale="0.5">
  <UseAttributeFromResidue name="charge"/>
  <Atom type="Fe2+_tip3p_standard" sigma="0.241077193129" epsilon="0.03940482832"/>
 </NonbondedForce>
</ForceField>"""

        pdb_string = "ATOM      1 FE    FE A   1      20.956  27.448 -29.067  1.00  0.00          Fe"
        pdb = PDBFile(StringIO(pdb_string))

        self.assertRaises(Exception, lambda: ForceField(StringIO(ffxml1), StringIO(ffxml2)))
        ff = ForceField(StringIO(ffxml1), StringIO(ffxml3))
        self.assertEqual(ff._templates['FE2'].atoms[0].type, 'Fe2+_tip3p_standard')
        ff.createSystem(pdb.topology)

    def test_CMAPTorsionGeneratorMapAssignment(self):
        """Tests assignment of the correct maps when multiple CMAPTorsionGenerators are present"""

        ffxml_1 = """
<ForceField>
    <AtomTypes>
        <Type name="A" class="A" element="C" mass="12" />
        <Type name="B" class="B" element="N" mass="14" />
    </AtomTypes>
    <Residues>
        <Residue name="X">
            <Atom name="X1" type="A" />
            <Atom name="X2" type="A" />
            <Atom name="X3" type="A" />
            <Atom name="X4" type="A" />
            <Atom name="X5" type="B" />
            <Bond atomName1="X1" atomName2="X2" />
            <Bond atomName1="X2" atomName2="X3" />
            <Bond atomName1="X3" atomName2="X4" />
            <Bond atomName1="X4" atomName2="X5" />
        </Residue>
        <Residue name="Y">
            <Atom name="Y1" type="A" />
            <Atom name="Y2" type="A" />
            <Atom name="Y3" type="A" />
            <Atom name="Y4" type="B" />
            <Atom name="Y5" type="B" />
            <Bond atomName1="Y1" atomName2="Y2" />
            <Bond atomName1="Y2" atomName2="Y3" />
            <Bond atomName1="Y3" atomName2="Y4" />
            <Bond atomName1="Y4" atomName2="Y5" />
        </Residue>
    </Residues>
    <CMAPTorsionForce>
        <Map>10 11 12 13</Map>
        <Torsion map="0" class1="A" class2="A" class3="A" class4="A" class5="B" />
    </CMAPTorsionForce>
</ForceField>
"""

        ffxml_2 = """
<ForceField>
    <CMAPTorsionForce>
        <Map>14 15 16 17</Map>
        <Torsion map="0" class1="A" class2="A" class3="A" class4="B" class5="B" />
    </CMAPTorsionForce>
</ForceField>
"""

        ff = ForceField(StringIO(ffxml_1), StringIO(ffxml_2))

        topology = Topology()

        x = topology.addResidue("X", topology.addChain())
        x1 = topology.addAtom("X1", elem.carbon, x)
        x2 = topology.addAtom("X2", elem.carbon, x)
        x3 = topology.addAtom("X3", elem.carbon, x)
        x4 = topology.addAtom("X4", elem.carbon, x)
        x5 = topology.addAtom("X5", elem.nitrogen, x)
        topology.addBond(x1, x2)
        topology.addBond(x2, x3)
        topology.addBond(x3, x4)
        topology.addBond(x4, x5)

        y = topology.addResidue("Y", topology.addChain())
        y1 = topology.addAtom("Y1", elem.carbon, y)
        y2 = topology.addAtom("Y2", elem.carbon, y)
        y3 = topology.addAtom("Y3", elem.carbon, y)
        y4 = topology.addAtom("Y4", elem.nitrogen, y)
        y5 = topology.addAtom("Y5", elem.nitrogen, y)
        topology.addBond(y1, y2)
        topology.addBond(y2, y3)
        topology.addBond(y3, y4)
        topology.addBond(y4, y5)

        system = ff.createSystem(topology)
        cmap, = (force for force in system.getForces() if isinstance(force, openmm.CMAPTorsionForce))

        torsionCount = cmap.getNumTorsions()
        assert torsionCount == 2

        for torsionIndex in range(torsionCount):
            mapIndex, *atomIndices = cmap.getTorsionParameters(torsionIndex)
            mapSize, energy = cmap.getMapParameters(mapIndex)

            if atomIndices == [0, 1, 2, 3, 1, 2, 3, 4]:
                expectedEnergy = (10.0, 11.0, 12.0, 13.0) * kilojoule_per_mole
            elif atomIndices == [5, 6, 7, 8, 6, 7, 8, 9]:
                expectedEnergy = (14.0, 15.0, 16.0, 17.0) * kilojoule_per_mole
            else:
                raise ValueError("unexpected torsion")

            assert energy == expectedEnergy

    def test_LennardJonesGenerator(self):
        """ Test the LennardJones generator"""
        warnings.filterwarnings('ignore', category=CharmmPSFWarning)
        psf = CharmmPsfFile('systems/ions.psf')
        pdb = PDBFile('systems/ions.pdb')
        params = CharmmParameterSet('systems/toppar_water_ions.str'
                                    )

        # Box dimensions (found from bounding box)
        psf.setBox(12.009*angstroms,   12.338*angstroms,   11.510*angstroms)

        # Turn off charges so we only test the Lennard-Jones energies
        for a in psf.atom_list:
            a.charge = 0.0

        # Now compute the full energy
        plat = Platform.getPlatform('Reference')
        system = psf.createSystem(params, nonbondedMethod=PME,
                                  nonbondedCutoff=5*angstroms)

        con = Context(system, VerletIntegrator(2*femtoseconds), plat)
        con.setPositions(pdb.positions)

        # Now set up system from ffxml.
        xml = """
<ForceField>
 <AtomTypes>
  <Type name="SOD" class="SOD" element="Na" mass="22.98977"/>
  <Type name="CLA" class="CLA" element="Cl" mass="35.45"/>
 </AtomTypes>
 <Residues>
  <Residue name="CLA">
   <Atom name="CLA" type="CLA"/>
  </Residue>
  <Residue name="SOD">
   <Atom name="SOD" type="SOD"/>
  </Residue>
 </Residues>
 <LennardJonesForce lj14scale="1.0" useDispersionCorrection="False">
  <Atom type="CLA" sigma="0.404468018036" epsilon="0.6276"/>
  <Atom type="SOD" sigma="0.251367073323" epsilon="0.1962296"/>
  <NBFixPair type1="CLA" type2="SOD" sigma="0.33239431" epsilon="0.350933"/>
 </LennardJonesForce>
</ForceField> """
        ff = ForceField(StringIO(xml))
        system2 = ff.createSystem(pdb.topology, nonbondedMethod=PME,
                                  nonbondedCutoff=5*angstroms)
        con2 = Context(system2, VerletIntegrator(2*femtoseconds), plat)
        con2.setPositions(pdb.positions)

        state = con.getState(getEnergy=True, enforcePeriodicBox=True)
        ene = state.getPotentialEnergy().value_in_unit(kilocalories_per_mole)
        state2 = con2.getState(getEnergy=True, enforcePeriodicBox=True)
        ene2 = state2.getPotentialEnergy().value_in_unit(kilocalories_per_mole)
        self.assertAlmostEqual(ene, ene2)

    def test_NBFix(self):
        """Test using LennardJonesGenerator to implement NBFix terms."""
        # Create a chain of seven atoms.

        top = Topology()
        chain = top.addChain()
        res = top.addResidue('RES', chain)
        top.addAtom('A', elem.carbon, res)
        top.addAtom('B', elem.nitrogen, res)
        top.addAtom('C', elem.nitrogen, res)
        top.addAtom('D', elem.oxygen, res)
        top.addAtom('E', elem.carbon, res)
        top.addAtom('F', elem.nitrogen, res)
        top.addAtom('G', elem.oxygen, res)
        atoms = list(top.atoms())
        top.addBond(atoms[0], atoms[1])
        top.addBond(atoms[1], atoms[2])
        top.addBond(atoms[2], atoms[3])
        top.addBond(atoms[3], atoms[4])
        top.addBond(atoms[4], atoms[5])
        top.addBond(atoms[5], atoms[6])

        # Create the force field and system.

        xml = """
<ForceField>
 <AtomTypes>
  <Type name="A" class="A" element="C" mass="1"/>
  <Type name="B" class="B" element="N" mass="1"/>
  <Type name="C" class="C" element="O" mass="1"/>
 </AtomTypes>
 <Residues>
  <Residue name="RES">
   <Atom name="A" type="A"/>
   <Atom name="B" type="B"/>
   <Atom name="C" type="B"/>
   <Atom name="D" type="C"/>
   <Atom name="E" type="A"/>
   <Atom name="F" type="B"/>
   <Atom name="G" type="C"/>
   <Bond atomName1="A" atomName2="B"/>
   <Bond atomName1="B" atomName2="C"/>
   <Bond atomName1="C" atomName2="D"/>
   <Bond atomName1="D" atomName2="E"/>
   <Bond atomName1="E" atomName2="F"/>
   <Bond atomName1="F" atomName2="G"/>
  </Residue>
 </Residues>
 <LennardJonesForce lj14scale="0.3">
  <Atom type="A" sigma="2.1" epsilon="1.1"/>
  <Atom type="B" sigma="2.2" epsilon="1.2"/>
  <Atom type="C" sigma="2.4" epsilon="1.4"/>
  <NBFixPair type1="C" type2="C" sigma="3.1" epsilon="4.1"/>
  <NBFixPair type1="A" type2="A" sigma="3.2" epsilon="4.2"/>
  <NBFixPair type1="B" type2="A" sigma="3.4" epsilon="4.4"/>
 </LennardJonesForce>
</ForceField> """
        ff = ForceField(StringIO(xml))
        system = ff.createSystem(top)

        # Check that it produces the correct energy.
        # The chain is A-B-B-C-A-B-C, and the pairs that are evaluated are:
        # A0-C3, A0-A4, A0-B5, A0-C6,
        # B1-A4, B1-B5, B1-C6,
        # B2-B5, B2-C6,
        # C3-C6.

        integrator = VerletIntegrator(0.001)
        context = Context(system, integrator, Platform.getPlatform(0))
        positions = [Vec3(i, 0, 0) for i in range(7)]*nanometers
        context.setPositions(positions)
        def ljEnergy(sigma, epsilon, r):
            return 4*epsilon*((sigma/r)**12-(sigma/r)**6)
        expected = 0.3*ljEnergy(2.25, math.sqrt(1.54), 3) + ljEnergy(3.2, 4.2, 4) + ljEnergy(3.4, 4.4, 5) + ljEnergy(2.25, math.sqrt(1.54), 6) \
                 + 0.3*ljEnergy(3.4, 4.4, 3) + ljEnergy(2.2, 1.2, 4) + ljEnergy(2.3, math.sqrt(1.68), 5) \
                 + 0.3*ljEnergy(2.2, 1.2, 3) + ljEnergy(2.3, math.sqrt(1.68), 4) \
                 + 0.3*ljEnergy(3.1, 4.1, 3)
        self.assertAlmostEqual(expected, context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(kilojoules_per_mole))

    def test_IgnoreExternalBonds(self):
        """Test the ignoreExternalBonds option"""

        modeller = Modeller(self.pdb2.topology, self.pdb2.positions)
        modeller.delete([next(modeller.topology.residues())])
        self.assertRaises(Exception, lambda: self.forcefield2.createSystem(modeller.topology))
        system = self.forcefield2.createSystem(modeller.topology, ignoreExternalBonds=True)
        templates = self.forcefield2.getMatchingTemplates(modeller.topology, ignoreExternalBonds=True)
        self.assertEqual(2, len(templates))
        self.assertEqual('ALA', templates[0].name)
        self.assertEqual('NME', templates[1].name)

    def test_Includes(self):
        """Test using a ForceField that includes other files."""
        forcefield = ForceField(os.path.join('systems', 'ff_with_includes.xml'))
        self.assertTrue(len(forcefield._atomTypes) > 10)
        self.assertTrue('spce-O' in forcefield._atomTypes)
        self.assertTrue('HOH' in forcefield._templates)

    def test_IncludesFromDataDirectory(self):
        """Test relative include paths from subdirectories of the data directory."""

        oldDataDirs = forcefield._dataDirectories
        try:
            with tempfile.TemporaryDirectory() as tempDataDir:
                forcefield._dataDirectories = forcefield._getDataDirectories() + [tempDataDir]
                os.mkdir(os.path.join(tempDataDir, 'subdir'))
                for testFileName in ['ff_with_includes.xml', 'test_amber_ff.xml']:
                    shutil.copyfile(os.path.join('systems', testFileName), os.path.join(tempDataDir, 'subdir', testFileName))
                ff = ForceField(os.path.join('subdir', 'ff_with_includes.xml'))
                self.assertTrue(len(ff._atomTypes) > 10)
                self.assertTrue('spce-O' in ff._atomTypes)
                self.assertTrue('HOH' in ff._templates)
        finally:
            forcefield._dataDirectories = oldDataDirs

    def test_ImpropersOrdering(self):
        """Test correctness of the ordering of atom indexes in improper torsions
        and the torsion.ordering parameter.
        """

        xml = """
<ForceField>
 <PeriodicTorsionForce ordering="amber">
  <Improper class1="C" class2="" class3="O2" class4="O2" periodicity1="2" phase1="3.14159265359" k1="43.932"/>
 </PeriodicTorsionForce>
</ForceField>
"""
        pdb = PDBFile('systems/impropers_ordering_tetrapeptide.pdb')
        # ff1 uses default ordering of impropers, ff2 uses "amber" for the one
        # problematic improper
        ff1 = ForceField('amber99sbildn.xml')
        ff2 = ForceField(StringIO(xml), 'amber99sbildn.xml')

        system1 = ff1.createSystem(pdb.topology)
        system2 = ff2.createSystem(pdb.topology)

        imp1 = system1.getForce(1).getTorsionParameters(158)
        imp2 = system2.getForce(0).getTorsionParameters(158)

        system1_indexes = [imp1[0], imp1[1], imp1[2], imp1[3]]
        system2_indexes = [imp2[0], imp2[1], imp2[2], imp2[3]]

        self.assertEqual(system1_indexes, [51, 55, 54, 56])
        self.assertEqual(system2_indexes, [51, 55, 54, 56])

    def test_ImpropersOrdering_smirnoff(self):
        """Test correctness of the ordering of atom indexes in improper torsions
        and the torsion.ordering parameter when using the 'smirnoff' mode.
        """

        # SMIRNOFF parameters for formaldehyde
        xml = """
<ForceField>
  <AtomTypes>
    <Type name="[H]C(=O)[H]$C1#0" element="C" mass="12.01078" class="[H]C(=O)[H]$C1#0"/>
    <Type name="[H]C(=O)[H]$O1#1" element="O" mass="15.99943" class="[H]C(=O)[H]$O1#1"/>
    <Type name="[H]C(=O)[H]$H1#2" element="H" mass="1.007947" class="[H]C(=O)[H]$H1#2"/>
    <Type name="[H]C(=O)[H]$H2#3" element="H" mass="1.007947" class="[H]C(=O)[H]$H2#3"/>
  </AtomTypes>
  <PeriodicTorsionForce ordering="smirnoff">
    <Improper class1="[H]C(=O)[H]$C1#0" class2="[H]C(=O)[H]$O1#1" class3="[H]C(=O)[H]$H1#2" class4="[H]C(=O)[H]$H2#3" periodicity1="2" phase1="3.141592653589793" k1="1.5341333333333336"/>
    <Improper class1="[H]C(=O)[H]$C1#0" class2="[H]C(=O)[H]$H1#2" class3="[H]C(=O)[H]$H2#3" class4="[H]C(=O)[H]$O1#1" periodicity1="2" phase1="3.141592653589793" k1="1.5341333333333336"/>
    <Improper class1="[H]C(=O)[H]$C1#0" class2="[H]C(=O)[H]$H2#3" class3="[H]C(=O)[H]$O1#1" class4="[H]C(=O)[H]$H1#2" periodicity1="2" phase1="3.141592653589793" k1="1.5341333333333336"/>
  </PeriodicTorsionForce>
  <Residues>
    <Residue name="[H]C(=O)[H]">
      <Atom name="C1" type="[H]C(=O)[H]$C1#0" charge="0.5632799863815308"/>
      <Atom name="O1" type="[H]C(=O)[H]$O1#1" charge="-0.514739990234375"/>
      <Atom name="H1" type="[H]C(=O)[H]$H1#2" charge="-0.02426999807357788"/>
      <Atom name="H2" type="[H]C(=O)[H]$H2#3" charge="-0.02426999807357788"/>
      <Bond atomName1="C1" atomName2="O1"/>
      <Bond atomName1="C1" atomName2="H1"/>
      <Bond atomName1="C1" atomName2="H2"/>
    </Residue>
  </Residues>
</ForceField>
"""
        pdb = PDBFile('systems/formaldehyde.pdb')
        # ff1 uses default ordering of impropers, ff2 uses "amber" for the one
        # problematic improper
        ff = ForceField(StringIO(xml))

        system = ff.createSystem(pdb.topology)

        # Check that impropers are applied in the correct three-fold trefoil pattern
        forces = { force.__class__.__name__ : force for force in system.getForces() }
        force = forces['PeriodicTorsionForce']
        created_torsions = set()
        for index in range(force.getNumTorsions()):
            i,j,k,l,_,_,_ = force.getTorsionParameters(index)
            created_torsions.add((i,j,k,l))
        expected_torsions = set([(0,3,1,2), (0,1,2,3), (0,2,3,1)])
        self.assertEqual(expected_torsions, created_torsions)

    def test_Disulfides(self):
        """Test that various force fields handle disulfides correctly."""
        pdb = PDBFile('systems/bpti.pdb')
        for ff in ['amber99sb.xml', 'amber14-all.xml', 'amber19-all.xml', 'charmm36.xml', 'charmm36_2024.xml', 'amberfb15.xml', 'amoeba2013.xml']:
            forcefield = ForceField(ff)
            system = forcefield.createSystem(pdb.topology)

    def test_IdenticalTemplates(self):
        """Test a case where patches produce two identical templates."""
        ff = ForceField('charmm36.xml')
        pdb = PDBFile(StringIO("""
ATOM      1  N   HIS     1A   -2.670    -0.476   0.475  1.00  0.00           N
ATOM      2  HT1 HIS     1A   -2.645    -1.336   1.036  1.00  0.00           H
ATOM      3  HT2 HIS     1A   -2.859    -0.751  -0.532  1.00  0.00           H
ATOM      4  HT3 HIS     1A   -3.415     0.201   0.731  1.00  0.00           H
ATOM      5  CA  HIS     1A   -1.347     0.163   0.471  1.00  0.00           C
ATOM      6  HA  HIS     1A   -1.111     0.506   1.479  1.00  0.00           H
ATOM      7  CB  HIS     1A   -0.352    -0.857  -0.040  1.00  0.00           C
ATOM      8  HB1 HIS     1A   -0.360    -1.741   0.636  1.00  0.00           H
ATOM      9  HB2 HIS     1A   -0.640    -1.175  -1.046  1.00  0.00           H
ATOM     10  CG  HIS     1A    1.003    -0.275  -0.063  1.00  0.00           C
ATOM     11  CD2 HIS     1A    2.143    -0.931  -0.476  1.00  0.00           C
ATOM     12  HD2 HIS     1A    2.217    -1.952  -0.840  1.00  0.00           H
ATOM     13  NE2 HIS     1A    3.137    -0.024  -0.328  1.00  0.00           N
ATOM     14  HE2 HIS     1A    4.132    -0.238  -0.565  1.00  0.00           H
ATOM     15  CE1 HIS     1A    2.649     1.130   0.150  1.00  0.00           C
ATOM     16  HE1 HIS     1A    3.233     2.020   0.360  1.00  0.00           H
ATOM     17  ND1 HIS     1A    1.323     0.973   0.314  1.00  0.00           N
ATOM     18  C   HIS     1A   -1.465     1.282  -0.497  1.00  0.00           C
ATOM     19  OT1 HIS     1A   -2.108     2.309  -0.180  1.00  0.00           O
ATOM     20  OT2 HIS     1A   -0.864     1.172  -1.737  1.00  0.00           O
END"""))
        # If the check is not done correctly, this will throw an exception.
        ff.createSystem(pdb.topology)
    
    def test_CharmmLoad(self):
        """Tests that the CHARMM force fields are capable of parameterizing systems."""

        charmm_models = ("charmm36", "charmm36_2024")
        water_models_3 = ("water", "spce", "tip3p-pme-b", "tip3p-pme-f")
        water_models_4 = ("tip4p2005", "tip4pew")
        water_models_5 = ("tip5p", "tip5pew")

        # Checks that the numbers of various types of terms in a system matches expected counts.
        def check_system(system, particle_count, site_count, constraint_count, bond_count, angle_count, cmap_count, exception_count, override_count, drude_count, screen_count):
            self.assertEqual(particle_count, system.getNumParticles())
            self.assertEqual(site_count, sum([1 for index in range(system.getNumParticles()) if system.isVirtualSite(index)]))
            self.assertEqual(constraint_count, system.getNumConstraints())
            self.assertEqual(bond_count, sum([force.getNumBonds() for force in system.getForces() if isinstance(force, HarmonicBondForce)]))
            self.assertEqual(angle_count, sum([force.getNumAngles() for force in system.getForces() if isinstance(force, HarmonicAngleForce)]))
            self.assertEqual(cmap_count, sum([force.getNumTorsions() for force in system.getForces() if isinstance(force, CMAPTorsionForce)]))
            self.assertEqual(exception_count, sum([force.getNumExceptions() for force in system.getForces() if isinstance(force, NonbondedForce)]))
            self.assertEqual(override_count, sum([force.getNumBonds() for force in system.getForces() if isinstance(force, CustomBondForce)]))
            self.assertEqual(drude_count, sum([force.getNumParticles() for force in system.getForces() if isinstance(force, DrudeForce)]))
            self.assertEqual(screen_count, sum([force.getNumScreenedPairs() for force in system.getForces() if isinstance(force, DrudeForce)]))

        # Standard 20 amino acids including N- and C-terminal variants.
        pdb_20aa = PDBFile("systems/test_charmm_20aa.pdb")
        for charmm_model in charmm_models:
            check_system(ForceField(f"{charmm_model}.xml").createSystem(pdb_20aa.topology), 1032, 0, 0, 1937, 1833, 20, 5390, 2527, 0, 0)

        # Standard 20 amino acids including N- and C-terminal variants (Drude).
        pdb_20aa_drude = PDBFile("systems/test_charmm_20aa_drude.pdb")
        for drude_model in ("charmm_polar_2019", "charmm_polar_2023"):
            check_system(ForceField(f"{drude_model}.xml").createSystem(pdb_20aa_drude.topology), 1794, 241, 0, 2106, 1833, 20, 18162, 7434, 521, 1203)

        # Peptide in water with ions.
        pdb_peptide_3 = PDBFile("systems/test_charmm_peptide_3.pdb")
        pdb_peptide_4 = PDBFile("systems/test_charmm_peptide_4.pdb")
        pdb_peptide_5 = PDBFile("systems/test_charmm_peptide_5.pdb")
        for charmm_model in charmm_models:
            for water_model in water_models_3:
                check_system(ForceField(f"{charmm_model}.xml", f"{charmm_model}/{water_model}.xml").createSystem(pdb_peptide_3.topology), 1136, 0, 984, 234, 249, 8, 1727, 353, 0, 0)
            for water_model in water_models_4:
                check_system(ForceField(f"{charmm_model}.xml", f"{charmm_model}/{water_model}.xml").createSystem(pdb_peptide_4.topology), 1464, 328, 984, 234, 249, 8, 2711, 353, 0, 0)
            for water_model in water_models_5:
                check_system(ForceField(f"{charmm_model}.xml", f"{charmm_model}/{water_model}.xml").createSystem(pdb_peptide_5.topology), 1792, 656, 984, 234, 249, 8, 4023, 353, 0, 0)

    def test_CharmmVersionMismatchCheck(self):
        """
        Tests that CHARMM force fields cannot be loaded with the wrong water model versions.
        """

        charmm_models = ("charmm36", "charmm36_2024")
        water_models = ("water", "spce", "tip3p-pme-b", "tip3p-pme-f", "tip4p2005", "tip4pew", "tip5p", "tip5pew")

        for base_charmm_model in charmm_models:
            for water_charmm_model in charmm_models:
                if base_charmm_model != water_charmm_model:
                    for water_model in water_models:
                        with self.assertRaises(Exception):
                            ForceField(f"{base_charmm_model}.xml", f"{water_charmm_model}/{water_model}.xml")
                        with self.assertRaises(Exception):
                            ForceField(f"{water_charmm_model}/{water_model}.xml", f"{base_charmm_model}.xml")

    def test_CharmmPolar(self):
        """Test the CHARMM polarizable force field."""
        pdb = PDBFile('systems/ala_ala_ala_drude.pdb')
        pdb.topology.setUnitCellDimensions(Vec3(3, 3, 3))
        ff = ForceField('charmm_polar_2019.xml')
        system = ff.createSystem(pdb.topology, nonbondedMethod=PME, nonbondedCutoff=1.2*nanometers)
        for i,f in enumerate(system.getForces()):
            f.setForceGroup(i)
            if isinstance(f, NonbondedForce):
                f.setPMEParameters(3.4, 64, 64, 64)
        integrator = DrudeLangevinIntegrator(300, 1.0, 1.0, 10.0, 0.001)
        context = Context(system, integrator, Platform.getPlatform('Reference'))
        context.setPositions(pdb.positions)

        # Compare the energy to values computed by CHARMM.  Here is what it outputs:

        # ENER ENR:  Eval#     ENERgy      Delta-E         GRMS
        # ENER INTERN:          BONDs       ANGLes       UREY-b    DIHEdrals    IMPRopers
        # ENER CROSS:           CMAPs        PMF1D        PMF2D        PRIMO
        # ENER EXTERN:        VDWaals         ELEC       HBONds          ASP         USER
        # ENER EWALD:          EWKSum       EWSElf       EWEXcl       EWQCor       EWUTil
        #  ----------       ---------    ---------    ---------    ---------    ---------
        # ENER>        0    102.83992      0.00000     13.06415
        # ENER INTERN>       54.72574     40.21459     11.61009     26.10373      0.14113
        # ENER CROSS>        -3.37113      0.00000      0.00000      0.00000
        # ENER EXTERN>       22.74761    -24.21667      0.00000      0.00000      0.00000
        # ENER EWALD>        56.14258  -7279.07968   7197.82192      0.00000      0.00000
        #  ----------       ---------    ---------    ---------    ---------    ---------

        # First check the total energy.
        
        energy = context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(kilocalories_per_mole)
        self.assertAlmostEqual(102.83992, energy, delta=energy*1e-3)

        # Now check individual components.  CHARMM and OpenMM split them up a little differently.  I've tried to
        # match things up, but I think there's still some inconsistency in where forces related to Drude particles
        # are categorized.  That's why the Coulomb and bonds terms match less accurately than the other terms
        # (and less accurately than the total energy, which agrees well).

        coulomb = 0
        vdw = 0
        bonds = 0
        angles = 0
        propers = 0
        impropers = 0
        cmap = 0
        for i,f in enumerate(system.getForces()):
            energy = context.getState(getEnergy=True, groups={i}).getPotentialEnergy().value_in_unit(kilocalories_per_mole)
            if isinstance(f, NonbondedForce):
                coulomb += energy
            elif isinstance(f, CustomNonbondedForce) or isinstance(f, CustomBondForce):
                vdw += energy
            elif isinstance(f, HarmonicBondForce) or isinstance(f, DrudeForce):
                bonds += energy
            elif isinstance(f, HarmonicAngleForce):
                angles += energy
            elif isinstance(f, PeriodicTorsionForce):
                propers += energy
            elif isinstance(f, CustomTorsionForce):
                impropers += energy
            elif isinstance(f, CMAPTorsionForce):
                cmap += energy
        self.assertAlmostEqual(-24.21667+56.14258-7279.07968+7197.82192, coulomb, delta=abs(coulomb)*5e-2) # ELEC+EWKSum+EWSElf+EWEXcl
        self.assertAlmostEqual(22.74761, vdw, delta=vdw*1e-3) # VDWaals
        self.assertAlmostEqual(54.72574+11.61009, bonds, delta=bonds*2e-2) # BONDs+UREY-b
        self.assertAlmostEqual(40.21459, angles, delta=angles*1e-3) # ANGLes
        self.assertAlmostEqual(26.10373, propers, delta=propers*1e-3) # DIHEdrals
        self.assertAlmostEqual(0.14113, impropers, delta=impropers*1e-3) # IMPRopers

    def test_InitializationScript(self):
        """Test that <InitializationScript> tags get executed."""
        xml = """
<ForceField>
  <InitializationScript>
self.scriptExecuted = True
  </InitializationScript>
</ForceField>
"""
        ff = ForceField(StringIO(xml))
        self.assertTrue(ff.scriptExecuted)

    def test_Glycam(self):
        """Test computing energy with GLYCAM."""
        ff = ForceField('amber14/protein.ff14SB.xml', 'amber14/GLYCAM_06j-1.xml')
        pdb = PDBFile('systems/glycopeptide.pdb')
        system = ff.createSystem(pdb.topology)
        for i, f in enumerate(system.getForces()):
            f.setForceGroup(i)
        integrator = VerletIntegrator(0.001)
        context = Context(system, integrator, Platform.getPlatform('Reference'))
        context.setPositions(pdb.positions)
        energies = {}
        for i, f in enumerate(system.getForces()):
            energy = context.getState(getEnergy=True, groups={i}).getPotentialEnergy().value_in_unit(kilojoules_per_mole)
            energies[f.getName()] = energy

        # Compare to values computed with ParmEd.

        self.assertAlmostEqual(32.14082401103625, energies['HarmonicBondForce'], 4)
        self.assertAlmostEqual(48.92017455984504, energies['HarmonicAngleForce'], 3)
        self.assertAlmostEqual(291.61241586209286, energies['PeriodicTorsionForce'], 4)
        self.assertAlmostEqual(1547.011267801862, energies['NonbondedForce'], 4)
        self.assertAlmostEqual(1919.6846822348361, sum(list(energies.values())), 3)

    def test_CustomNonbondedGenerator(self):
        """ Test the CustomNonbondedForce generator"""
        pdb = PDBFile('systems/ions.pdb')
        xml = """
<ForceField>
 <AtomTypes>
  <Type name="SOD" class="SOD" element="Na" mass="22.98977"/>
  <Type name="CLA" class="CLA" element="Cl" mass="35.45"/>
 </AtomTypes>
 <Residues>
  <Residue name="CLA">
   <Atom name="CLA" type="CLA"/>
  </Residue>
  <Residue name="SOD">
   <Atom name="SOD" type="SOD"/>
  </Residue>
 </Residues>
 <CustomNonbondedForce energy="scale*epsilon*((sigma/r)^12-(sigma/r)^6); sigma=halfSig1+halfSig2; epsilon=rootEps1*rootEps2" bondCutoff="3">
  <GlobalParameter name="scale" defaultValue="4"/>
  <PerParticleParameter name="sigma"/>
  <PerParticleParameter name="epsilon"/>
  <ComputedValue name="halfSig" expression="0.5*sigma"/>
  <ComputedValue name="rootEps" expression="sqrt(epsilon)"/>
  <Atom type="CLA" sigma="0.404468018036" epsilon="0.6276"/>
  <Atom type="SOD" sigma="0.251367073323" epsilon="0.1962296"/>
 </CustomNonbondedForce>
</ForceField> """
        ff = ForceField(StringIO(xml))
        system = ff.createSystem(pdb.topology)
        context = Context(system, VerletIntegrator(2*femtoseconds), Platform.getPlatform('Reference'))
        context.setPositions(pdb.positions)
        energy1 = context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(kilojoules_per_mole)

        # See if it matches an equivalent NonbondedForce.
        
        system = System()
        system.addParticle(1.0)
        system.addParticle(1.0)
        f = NonbondedForce()
        f.addParticle(0, 0.404468018036, 0.6276)
        f.addParticle(0, 0.251367073323, 0.1962296)
        system.addForce(f)
        context = Context(system, VerletIntegrator(2*femtoseconds), Platform.getPlatform('Reference'))
        context.setPositions(pdb.positions)
        energy2 = context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(kilojoules_per_mole)
        self.assertAlmostEqual(energy1, energy2)

    def test_OpcEnergy(self):
        pdb = PDBFile('systems/opcbox.pdb')
        topology, positions = pdb.topology, pdb.positions
        self.assertEqual(len(positions), 864)
        forcefield = ForceField('opc.xml')
        system = forcefield.createSystem(
            topology,
            nonbondedMethod=PME,
            nonbondedCutoff=0.7*nanometer,
            constraints=HBonds,
            rigidWater=True,
        )

        integrator = LangevinIntegrator(300*kelvin, 2.0/picoseconds, 2.0*femtoseconds)
        simulation = Simulation(topology, system, integrator)
        context = simulation.context
        context.setPositions(positions)

        # Compare to values computed with Amber (sander).
        energy_amber = -2647.6233 # kcal/mol
        energy_tolerance = 1.0

        state = context.getState(getEnergy=True)
        energy1 = state.getPotentialEnergy().value_in_unit(kilocalorie_per_mole)
        # -2647.2222697324237
        self.assertTrue(abs(energy1 - energy_amber) < energy_tolerance)

        context.applyConstraints(1e-12)
        state = context.getState(getEnergy=True)
        energy2 = state.getPotentialEnergy().value_in_unit(kilocalorie_per_mole)
        # -2647.441600693312
        self.assertTrue(abs(energy1 - energy_amber) < energy_tolerance)
        self.assertTrue(abs(energy1 - energy2) < energy_tolerance)

    def test_Opc3Energy(self):
        pdb = PDBFile('systems/opc3box.pdb')
        topology, positions = pdb.topology, pdb.positions
        self.assertEqual(len(positions), 648)
        forcefield = ForceField('opc3.xml')
        system = forcefield.createSystem(
            topology,
            nonbondedMethod=PME,
            nonbondedCutoff=0.7*nanometer,
            constraints=HBonds,
            rigidWater=True,
        )

        integrator = LangevinIntegrator(300*kelvin, 2.0/picoseconds, 2.0*femtoseconds)
        simulation = Simulation(topology, system, integrator)
        context = simulation.context
        context.setPositions(positions)

        # Compare to values computed with Amber (sander).
        energy_amber = -2532.1414 # kcal/mol
        energy_tolerance = 1.0

        state = context.getState(getEnergy=True)
        energy1 = state.getPotentialEnergy().value_in_unit(kilocalorie_per_mole)
        # -2532.4862082354407
        self.assertTrue(abs(energy1 - energy_amber) < energy_tolerance)

        context.applyConstraints(1e-12)
        state = context.getState(getEnergy=True)
        energy2 = state.getPotentialEnergy().value_in_unit(kilocalorie_per_mole)
        self.assertTrue(abs(energy1 - energy_amber) < energy_tolerance)
        self.assertTrue(abs(energy1 - energy2) < energy_tolerance)


class AmoebaTestForceField(unittest.TestCase):
    """Test the ForceField.createSystem() method with the AMOEBA forcefield."""

    def setUp(self):
        """Set up the tests by loading the input pdb files and force field
        xml files.

        """

        self.pdb1 = PDBFile('systems/amoeba-ion-in-water.pdb')
        self.forcefield1 = ForceField('amoeba2013.xml')
        self.topology1 = self.pdb1.topology


    def test_NonbondedMethod(self):
        """Test both options for the nonbondedMethod parameter."""

        methodMap = {NoCutoff:AmoebaMultipoleForce.NoCutoff,
                     PME:AmoebaMultipoleForce.PME}

        for method in methodMap:
            system = self.forcefield1.createSystem(self.pdb1.topology,
                                                  nonbondedMethod=method)
            forces = system.getForces()
            self.assertTrue(any(isinstance(f, AmoebaMultipoleForce) and
                                f.getNonbondedMethod()==methodMap[method]
                                for f in forces))
    def test_Cutoff(self):
        """Test to make sure the nonbondedCutoff parameter is passed correctly."""

        cutoff_distance = 0.7*nanometer
        for method in [NoCutoff, PME]:
            system = self.forcefield1.createSystem(self.pdb1.topology,
                                                   nonbondedMethod=method,
                                                   nonbondedCutoff=cutoff_distance,
                                                   constraints=None)

            for force in system.getForces():
                if isinstance(force, AmoebaVdwForce):
                    self.assertEqual(force.getCutoff(), cutoff_distance)
                if isinstance(force, AmoebaMultipoleForce):
                    self.assertEqual(force.getCutoffDistance(), cutoff_distance)

    def test_DispersionCorrection(self):
        """Test to make sure the nonbondedCutoff parameter is passed correctly."""

        for useDispersionCorrection in [True, False]:
            system = self.forcefield1.createSystem(self.pdb1.topology,
                                                   nonbondedMethod=PME,
                                                   useDispersionCorrection=useDispersionCorrection)

            for force in system.getForces():
                if isinstance(force, AmoebaVdwForce):
                    self.assertEqual(useDispersionCorrection, force.getUseDispersionCorrection())

    def test_RigidWater(self):
        """Test that AMOEBA creates rigid water with the correct geometry."""

        system = self.forcefield1.createSystem(self.pdb1.topology, rigidWater=True)
        constraints = dict()
        for i in range(system.getNumConstraints()):
            p1,p2,dist = system.getConstraintParameters(i)
            if p1 < 3:
                constraints[(min(p1,p2), max(p1,p2))] = dist.value_in_unit(nanometers)
        hoDist = 0.09572
        hohAngle = 108.50*math.pi/180.0
        hohDist = math.sqrt(2*hoDist**2 - 2*hoDist**2*math.cos(hohAngle))
        self.assertAlmostEqual(constraints[(0,1)], hoDist)
        self.assertAlmostEqual(constraints[(0,2)], hoDist)
        self.assertAlmostEqual(constraints[(1,2)], hohDist)
        
        # Check that all values of rigidWater are interpreted correctly.
        
        numWaters = 215
        self.assertEqual(3*numWaters, system.getNumConstraints())
        system = self.forcefield1.createSystem(self.pdb1.topology, rigidWater=False)
        self.assertEqual(0, system.getNumConstraints())
        system = self.forcefield1.createSystem(self.pdb1.topology, rigidWater=None)
        self.assertEqual(0, system.getNumConstraints())

    def test_Forces(self):
        """Compute forces and compare them to ones generated with a previous version of OpenMM to ensure they haven't changed."""

        pdb = PDBFile('systems/alanine-dipeptide-implicit.pdb')
        forcefield = ForceField('amoeba2013.xml', 'amoeba2013_gk.xml')
        system = forcefield.createSystem(pdb.topology, polarization='direct')
        integrator = VerletIntegrator(0.001)
        context = Context(system, integrator, Platform.getPlatform('Reference'))
        context.setPositions(pdb.positions)
        state1 = context.getState(getForces=True)
        with open('systems/alanine-dipeptide-amoeba-forces.xml') as input:
            state2 = XmlSerializer.deserialize(input.read())
        for f1, f2, in zip(state1.getForces().value_in_unit(kilojoules_per_mole/nanometer), state2.getForces().value_in_unit(kilojoules_per_mole/nanometer)):
            diff = norm(f1-f2)
            self.assertTrue(diff < 0.1 or diff/norm(f1) < 1e-3)

    def computeAmoeba18Energies(self, filename):
        pdb = PDBFile(filename)
        forcefield = ForceField('amoeba2018.xml')
        system = forcefield.createSystem(pdb.topology, polarization='mutual', mutualInducedTargetEpsilon=1e-5)
        for i, f in enumerate(system.getForces()):
            f.setForceGroup(i)
        integrator = VerletIntegrator(0.001)
        context = Context(system, integrator, Platform.getPlatform('Reference'))
        context.setPositions(pdb.positions)
        energies = {}
        for i, f in enumerate(system.getForces()):
            state = context.getState(getEnergy=True, groups={i})
            energies[f.getName()] = state.getPotentialEnergy().value_in_unit(kilocalories_per_mole)
        return energies

    def test_Amoeba18BPTI(self):
        """Test that AMOEBA18 computes energies correctly for BPTI."""
        energies = self.computeAmoeba18Energies('systems/bpti.pdb')

        # Compare to values computed with Tinker.

        self.assertAlmostEqual(290.2445, energies['AmoebaBond'], 4)
        self.assertAlmostEqual(496.4300, energies['AmoebaAngle']+energies['AmoebaInPlaneAngle'], 4)
        self.assertAlmostEqual(51.2913, energies['AmoebaOutOfPlaneBend'], 4)
        self.assertAlmostEqual(5.7695, energies['AmoebaStretchBend'], 4)
        self.assertAlmostEqual(75.6890, energies['PeriodicTorsionForce'], 4)
        self.assertAlmostEqual(19.3364, energies['AmoebaPiTorsion'], 4)
        self.assertAlmostEqual(-32.6689, energies['AmoebaTorsionTorsionForce'], 4)
        self.assertAlmostEqual(383.8705, energies['AmoebaVdwForce'], 4)
        self.assertAlmostEqual(-1323.5640-225.3660, energies['AmoebaMultipoleForce'], 2)
        self.assertAlmostEqual(-258.9676, sum(list(energies.values())), 2)

    def test_Amoeba18Nucleic(self):
        """Test that AMOEBA18 computes energies correctly for DNA and RNA."""
        energies = self.computeAmoeba18Energies('systems/nucleic.pdb')

        # Compare to values computed with Tinker.

        self.assertAlmostEqual(749.6953, energies['AmoebaBond'], 4)
        self.assertAlmostEqual(579.9971, energies['AmoebaAngle']+energies['AmoebaInPlaneAngle'], 4)
        self.assertAlmostEqual(10.6630, energies['AmoebaOutOfPlaneBend'], 4)
        self.assertAlmostEqual(5.2225, energies['AmoebaStretchBend'], 4)
        self.assertAlmostEqual(166.7233, energies['PeriodicTorsionForce'], 4)
        self.assertAlmostEqual(57.2066, energies['AmoebaPiTorsion'], 4)
        self.assertAlmostEqual(-4.2538, energies['AmoebaStretchTorsion'], 4)
        self.assertAlmostEqual(-5.0402, energies['AmoebaAngleTorsion'], 4)
        self.assertAlmostEqual(187.1103, energies['AmoebaVdwForce'], 4)
        self.assertAlmostEqual(1635.1289-236.1484, energies['AmoebaMultipoleForce'], 3)
        self.assertAlmostEqual(3146.3046, sum(list(energies.values())), 3)

if __name__ == '__main__':
    unittest.main()
