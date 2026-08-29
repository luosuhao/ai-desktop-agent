import java.util.List;

public class Main {
    public static void main(String[] args) {
        // Initialize GradeManager and add students
        GradeManager gm = new GradeManager();

        // Add students with multiple subjects
        Student alice = new Student("Alice", "Math", 90);
        alice.addSubject("English", 85);
        gm.addStudent(alice);

        Student bob = new Student("Bob", "Math", 85);
        bob.addSubject("English", 92);
        gm.addStudent(bob);

        Student charlie = new Student("Charlie", "English", 78);
        charlie.addSubject("Math", 70);
        gm.addStudent(charlie);

        Student david = new Student("David", "Math", 55);
        david.addSubject("English", 60);
        gm.addStudent(david);

        System.out.println("=== Test getAverageGrade(String subject) ===");
        System.out.println("Average Math grade: " + gm.getAverageGrade("Math"));
        // Alice(90) + Bob(85) + Charlie(70) + David(55) = 300 / 4 = 75.0
        System.out.println("Average English grade: " + gm.getAverageGrade("English"));
        // Alice(85) + Bob(92) + Charlie(78) + David(60) = 315 / 4 = 78.75

        System.out.println("\n=== Test getPassRate(double passingScore) ===");
        System.out.println("Pass rate (>= 60): " + gm.getPassRate(60.0) + "%");
        // Alice(90,85), Bob(85,92), Charlie(78,70), David(55,60) -> all 4 pass at least one subject >= 60
        System.out.println("Pass rate (>= 80): " + gm.getPassRate(80.0) + "%");
        // Alice(90), Bob(85,92) -> 2 out of 4 pass at least one subject >= 80 => 50%

        System.out.println("\n=== Test removeStudent(String name) ===");
        System.out.println("Before removal:");
        List<Student> allStudents = gm.getAllStudents();
        for (Student s : allStudents) {
            System.out.println("  " + s.getName() + " - Subject: " + s.getSubject() + ", Grade: " + s.getGrade(s.getSubject()));
        }

        gm.removeStudent("Alice");
        System.out.println("\nAfter removing Alice:");
        allStudents = gm.getAllStudents();
        for (Student s : allStudents) {
            System.out.println("  " + s.getName() + " - Subject: " + s.getSubject() + ", Grade: " + s.getGrade(s.getSubject()));
        }

        System.out.println("\nAverage Math grade after removal: " + gm.getAverageGrade("Math"));
        // Bob(85) + Charlie(70) + David(55) = 210 / 3 = 70.0

        System.out.println("\n=== All tests completed! ===");
    }
}
