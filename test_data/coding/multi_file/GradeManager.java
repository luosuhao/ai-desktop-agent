import java.util.ArrayList;
import java.util.List;

public class GradeManager {
    private List<Student> students = new ArrayList<>();

    public void addStudent(Student student) {
        students.add(student);
    }

    public double getAverageGrade(String subject) {
        double sum = 0.0;
        int count = 0;
        for (Student s : students) {
            if (s.getSubjects().containsKey(subject)) {
                sum += s.getSubjects().get(subject);
                count++;
            }
        }
        return count > 0 ? sum / count : 0.0;
    }

    public double getPassRate(double passingScore) {
        if (students.isEmpty()) {
            return 0.0;
        }
        int passCount = 0;
        for (Student s : students) {
            boolean passed = false;
            for (double grade : s.getSubjects().values()) {
                if (grade >= passingScore) {
                    passed = true;
                    break;
                }
            }
            if (passed) {
                passCount++;
            }
        }
        return ((double) passCount / students.size()) * 100;
    }

    public void removeStudent(String name) {
        students.removeIf(s -> s.getName().equals(name));
    }

    public List<Student> getAllStudents() {
        return new ArrayList<>(students);
    }
}
